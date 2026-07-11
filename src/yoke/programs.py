"""Yoke-owned Claude-style workflow runtime."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
from collections.abc import Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from yoke.models import (
    Failure,
    Harness,
    Run,
    RunStatus,
    Workflow,
    WorkflowRun,
    WorkflowRunMode,
    WorkflowTrace,
)
from yoke.options import RunOptions, WorkflowOptions
from yoke.workflows import merge_agent, merge_run_options


class WorkflowMemory:
    """In-memory replay store for Yoke workflow agent calls."""

    def __init__(self) -> None:
        self._runs: dict[tuple[str, str], Run] = {}

    def get(self, run_id: str, key: str) -> Run | None:
        """Return a cached run for this flow run id and call key."""

        return self._runs.get((run_id, key))

    def put(self, run_id: str, key: str, run: Run) -> None:
        """Store a run for later resume/replay."""

        self._runs[(run_id, key)] = run


class WorkflowStore:
    """JSONL-backed replay store for Yoke workflow agent calls."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def get(self, run_id: str, key: str) -> Run | None:
        """Return a cached run for this flow run id and call key."""

        if not self.path.exists():
            return None
        found: Run | None = None
        with self.path.open() as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("run_id") == run_id and record.get("key") == key:
                    found = Run.model_validate(record["run"])
        return found

    def put(self, run_id: str, key: str, run: Run) -> None:
        """Append a cached run record."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "run_id": run_id,
            "key": key,
            "run": run.model_dump(mode="json", exclude={"provider_session_id"}),
        }
        with self.path.open("a") as file:
            file.write(json.dumps(record, sort_keys=True) + "\n")


async def run_program(
    harness: Harness,
    workflow: Workflow,
    args: Any,
    options: WorkflowOptions,
) -> WorkflowRun:
    """Run a Yoke workflow program."""

    handler = workflow.handler or load_program_handler(workflow)
    if handler is None:
        raise ValueError(f"workflow {workflow.name!r} has no handler")
    run_id = options.resume or str(uuid4())
    context = WorkflowContext(harness, workflow, args, options, run_id)
    try:
        value = handler(context)
        result = await maybe_await(value)
    except Exception as exc:
        return WorkflowRun(
            workflow=workflow.name,
            mode=WorkflowRunMode.YOKE_PORTABLE,
            run_id=run_id,
            resume_from_run_id=options.resume,
            provider=harness.provider,
            surface=harness.surface,
            status=RunStatus.FAILED,
            output=str(exc),
            traces=tuple(context.traces),
            failure=Failure(message=str(exc), raw=repr(exc)),
        )
    output, data = workflow_output(result)
    return WorkflowRun(
        workflow=workflow.name,
        mode=WorkflowRunMode.YOKE_PORTABLE,
        run_id=run_id,
        resume_from_run_id=options.resume,
        provider=harness.provider,
        surface=harness.surface,
        output=output,
        data=data,
        traces=tuple(context.traces),
    )


class WorkflowContext:
    """Runtime helpers available inside a Yoke workflow program."""

    def __init__(
        self,
        harness: Harness,
        workflow: Workflow,
        args: Any,
        options: WorkflowOptions,
        run_id: str,
    ) -> None:
        self.harness = harness
        self.workflow = workflow
        self.args = args
        self.options = options
        self.run_id = run_id
        self.traces: list[WorkflowTrace] = []
        self._phase: str | None = None

    async def agent(
        self,
        agent: str,
        prompt: str,
        *,
        options: RunOptions | dict[str, Any] | None = None,
    ) -> Run:
        """Run one agent turn inside this flow."""

        step_harness = harness_for_agent(self.harness, agent)
        run_options = merge_run_options(self.options.run, options)
        cache_key = agent_cache_key(agent, prompt, self._phase, run_options)
        cached = (
            self.options.memory.get(self.run_id, cache_key)
            if self.options.memory is not None
            else None
        )
        if cached is not None:
            run = cached
            cached_hit = True
        else:
            run = await step_harness.run(prompt, run_options)
            if self.options.memory is not None and run.ok:
                self.options.memory.put(self.run_id, cache_key, run)
            cached_hit = False
        self.traces.append(
            WorkflowTrace(
                kind="agent",
                id=self.run_id,
                cached=cached_hit,
                name=agent,
                phase=self._phase,
                agent=agent,
                prompt=prompt,
                output=run.output,
                data=run.data,
                run=run,
            )
        )
        if self.options.fail_fast and not run.ok:
            raise RuntimeError(run.output or f"workflow agent {agent!r} failed")
        return run

    async def parallel(self, *items: Awaitable[Any]) -> tuple[Any, ...]:
        """Run awaitables concurrently and return ordered results."""

        results = await asyncio.gather(*items)
        self.traces.append(
            WorkflowTrace(
                kind="parallel",
                id=self.run_id,
                phase=self._phase,
                data={"count": len(items)},
            )
        )
        return tuple(results)

    async def pipeline(
        self,
        items: Iterable[Any],
        worker: Callable[[Any], Awaitable[Any] | Any],
        *,
        phase: str | None = None,
        concurrency: int | None = None,
    ) -> tuple[Any, ...]:
        """Map `worker` over items with bounded concurrency."""

        values = tuple(items)
        limit = concurrency or self.options.concurrency
        semaphore = asyncio.Semaphore(limit)

        async def one(item: Any) -> Any:
            async with semaphore:
                return await maybe_await(worker(item))

        pipeline_phase = phase or self._phase
        async with (self.phase(phase) if phase else null_phase()):
            results = await asyncio.gather(*[one(item) for item in values])
        self.traces.append(
            WorkflowTrace(
                kind="pipeline",
                id=self.run_id,
                name=phase,
                phase=pipeline_phase,
                data={"count": len(values), "concurrency": limit},
            )
        )
        return tuple(results)

    @asynccontextmanager
    async def phase(self, name: str):
        """Group subsequent flow activity under a named phase."""

        previous = self._phase
        self._phase = name
        self.traces.append(
            WorkflowTrace(kind="phase_start", id=self.run_id, name=name, phase=name)
        )
        try:
            yield self
        finally:
            self.traces.append(
                WorkflowTrace(kind="phase_end", id=self.run_id, name=name, phase=name)
            )
            self._phase = previous

    def summarize(self, values: Iterable[Any], *, separator: str = "\n") -> str:
        """Return a compact text summary from runs or arbitrary values."""

        parts: list[str] = []
        for value in values:
            if isinstance(value, Run):
                if value.output:
                    parts.append(value.output)
            elif value is not None:
                parts.append(str(value))
        output = separator.join(parts)
        self.traces.append(
            WorkflowTrace(
                kind="summary",
                id=self.run_id,
                phase=self._phase,
                output=output,
            )
        )
        return output


@asynccontextmanager
async def null_phase():
    yield None


async def maybe_await(value: Awaitable[Any] | Any) -> Any:
    """Await awaitables and return plain values unchanged."""

    if inspect.isawaitable(value):
        return await value
    return value


def harness_for_agent(harness: Harness, name: str) -> Harness:
    """Return a harness bound to the requested workflow agent."""

    if name in ("", "main", "root"):
        return harness
    try:
        agent = harness.agent.subagents[name]
    except KeyError as exc:
        raise ValueError(f"workflow references unknown agent {name!r}") from exc
    return harness.model_copy(update={"agent": merge_agent(harness.agent, agent)})


def workflow_output(value: Any) -> tuple[str | None, Any | None]:
    """Normalize a handler return value into WorkflowRun output/data."""

    if isinstance(value, Run):
        return value.output, value.data
    if isinstance(value, str):
        return value, None
    return (None if value is None else str(value)), value


def load_program_handler(workflow: Workflow) -> Callable[..., Any] | None:
    """Load a Python workflow program handler from ``workflow.py``."""

    if workflow.program_path is None:
        return None
    path = workflow.program_path
    spec = importlib.util.spec_from_file_location(
        f"yoke_workflow_{workflow.name.replace('-', '_')}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load workflow program from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = getattr(module, "main", None)
    if handler is None:
        raise ValueError(f"{path} must define main(ctx)")
    if not callable(handler):
        raise ValueError(f"{path} main must be callable")
    return handler


def agent_cache_key(
    agent: str,
    prompt: str,
    phase: str | None,
    options: RunOptions,
) -> str:
    """Return a stable replay key for one workflow agent call."""

    payload = {
        "agent": agent,
        "phase": phase,
        "prompt": prompt,
        "options": options.model_dump(mode="json", exclude_none=True),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
