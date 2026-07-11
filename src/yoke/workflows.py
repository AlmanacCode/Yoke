"""Yoke-owned workflow orchestration."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from string import Formatter

from yoke.capabilities import Feature
from yoke.errors import UnsupportedFeature
from yoke.models import (
    Agent,
    Failure,
    Harness,
    Run,
    RunStatus,
    Step,
    StepResult,
    Workflow,
    WorkflowRun,
    WorkflowRunMode,
    WorkflowTrace,
)
from yoke.options import RunOptions, WorkflowOptions


async def run_workflow(
    harness: Harness,
    workflow: Workflow,
    prompt: object,
    options: WorkflowOptions,
) -> WorkflowRun:
    """Run a workflow over provider harness calls.

    This is deliberately provider-neutral orchestration. It does not claim the
    provider has a native workflow primitive.
    """

    if workflow.handler is not None or workflow.program_path is not None:
        return await run_bounded_workflow(
            run_program_workflow(harness, workflow, prompt, options),
            harness,
            workflow,
            options,
            active_step="program",
    )
    if workflow.native or options.native:
        return await run_bounded_workflow(
            run_native_workflow(harness, workflow, prompt, options),
            harness,
            workflow,
            options,
            active_step="native",
        )
    if not workflow.steps:
        raise ValueError("workflow has no body")

    validate_workflow_steps(workflow)
    state = WorkflowState(
        pending={step.name: step for step in workflow.steps},
    )
    try:
        async with asyncio.timeout(options.timeout_seconds):
            return await run_portable_workflow(
                harness, workflow, prompt, options, state
            )
    except TimeoutError:
        active = ordered_step_names(workflow, state.active)
        await cancel_tasks(state.tasks.values())
        for name in active:
            await emit_trace(
                state,
                options,
                WorkflowTrace(kind="step_timed_out", name=name),
            )
        failed_name = active[0] if active else None
        failure = Failure(message="workflow timed out")
        ordered = ordered_results(workflow, state.results)
        return WorkflowRun(
            workflow=workflow.name,
            provider=harness.provider,
            surface=harness.surface,
            status=RunStatus.FAILED,
            steps=tuple(ordered),
            traces=tuple(state.traces),
            output=ordered[-1].run.output if ordered else None,
            failure=failure,
            failed_step_name=failed_name,
            interrupted_steps=active,
        )
    except BaseException:
        await cancel_tasks(state.tasks.values())
        raise


@dataclass
class WorkflowState:
    """Mutable execution evidence retained if orchestration is interrupted."""

    pending: dict[str, Step]
    outputs: dict[str, str] = field(default_factory=dict)
    results: list[StepResult] = field(default_factory=list)
    traces: list[WorkflowTrace] = field(default_factory=list)
    tasks: dict[str, asyncio.Task[tuple[StepResult, str]]] = field(
        default_factory=dict
    )
    active: set[str] = field(default_factory=set)
    rendered: dict[str, str] = field(default_factory=dict)


async def run_portable_workflow(
    harness: Harness,
    workflow: Workflow,
    prompt: object,
    options: WorkflowOptions,
    state: WorkflowState,
) -> WorkflowRun:
    """Schedule portable workflow steps with bounded concurrency."""

    while state.pending or state.tasks:
        ready = [
            step
            for step in workflow.steps
            if step.name in state.pending
            and dependencies_for_step(step).issubset(state.outputs.keys())
        ]
        slots = options.concurrency - len(state.tasks)
        for step in ready[:slots]:
            state.pending.pop(step.name)
            state.active.add(step.name)
            rendered = render_prompt(step, prompt, state.outputs)
            state.rendered[step.name] = rendered
            await emit_trace(
                state,
                options,
                WorkflowTrace(
                    kind="step_started",
                    name=step.name,
                    agent=step.agent or "main",
                    prompt=rendered,
                ),
            )
            state.tasks[step.name] = asyncio.create_task(
                run_step_bounded(
                    harness, step, prompt, state.outputs, options, rendered
                ),
                name=f"yoke-workflow:{workflow.name}:{step.name}",
            )
        if not state.tasks:
            raise_unresolved_dependencies(state.pending, state.outputs)
        done, _ = await asyncio.wait(
            state.tasks.values(), return_when=asyncio.FIRST_COMPLETED
        )
        done_names = ordered_step_names(
            workflow,
            {
                name
                for name, task in state.tasks.items()
                if task in done
            },
        )
        batch_results: list[StepResult] = []
        for name in done_names:
            task = state.tasks.pop(name)
            state.active.discard(name)
            try:
                result, event_kind = task.result()
            except Exception as exc:
                result = exception_step_result(
                    harness,
                    step_by_name(workflow, name),
                    state.rendered[name],
                    exc,
                )
                event_kind = "step_failed"
            batch_results.append(result)
            output = result.run.output or ""
            state.outputs[result.step] = output
            state.results.append(result)
            await emit_trace(
                state,
                options,
                WorkflowTrace(
                    kind=event_kind,
                    name=result.step,
                    agent=result.agent,
                    prompt=result.prompt,
                    output=result.run.output,
                    data=result.run.data,
                    run=result.run,
                ),
            )
        failure = first_failure(batch_results)
        if failure is not None and options.fail_fast:
            failed = failed_step_result(batch_results)
            active = ordered_step_names(workflow, state.active)
            await cancel_tasks(state.tasks.values())
            return failed_workflow(
                workflow,
                ordered_results(workflow, state.results),
                failed.run.output if failed else "",
                failure,
                harness=harness,
                traces=state.traces,
                failed_step_name=failed.step if failed else None,
                interrupted_steps=active,
            )
    ordered = ordered_results(workflow, state.results)
    final = ordered[-1].run.output if ordered else None
    data = ordered[-1].run.data if ordered else None
    failure = first_failure(state.results)
    return WorkflowRun(
        workflow=workflow.name,
        provider=harness.provider,
        surface=harness.surface,
        status=RunStatus.FAILED if failure else RunStatus.SUCCEEDED,
        steps=tuple(ordered),
        output=final,
        data=data,
        failure=failure,
        traces=tuple(state.traces),
        failed_step_name=(
            failed_step_result(state.results).step
            if failed_step_result(state.results) is not None
            else None
        ),
        )


async def run_bounded_workflow(
    operation,
    harness: Harness,
    workflow: Workflow,
    options: WorkflowOptions,
    *,
    active_step: str,
) -> WorkflowRun:
    """Apply the overall workflow bound to program and native workflows."""

    try:
        async with asyncio.timeout(options.timeout_seconds):
            return await operation
    except TimeoutError:
        return WorkflowRun(
            workflow=workflow.name,
            provider=harness.provider,
            surface=harness.surface,
            status=RunStatus.FAILED,
            failure=Failure(message="workflow timed out"),
            failed_step_name=active_step,
            interrupted_steps=(active_step,),
        )


async def run_program_workflow(
    harness: Harness,
    workflow: Workflow,
    args: object,
    options: WorkflowOptions,
) -> WorkflowRun:
    """Run a Python-authored Claude-style workflow program."""

    from yoke.programs import run_program

    program_args = workflow.args if args is None else args
    return await run_program(harness, workflow, program_args, options)


async def run_native_workflow(
    harness: Harness,
    workflow: Workflow,
    prompt: str,
    options: WorkflowOptions,
) -> WorkflowRun:
    """Delegate a provider-native workflow to the selected adapter."""

    from yoke.adapters import adapter_for

    try:
        return await adapter_for(harness.provider, harness.surface).workflow(
            harness,
            workflow,
            prompt,
            options,
        )
    except AttributeError as exc:
        raise native_workflow_unsupported(harness, workflow, options) from exc


def native_workflow_unsupported(
    harness: Harness,
    workflow: Workflow,
    options: WorkflowOptions,
    *,
    reason: str | None = None,
) -> UnsupportedFeature:
    """Return the standard provider-native workflow boundary error."""

    body = native_workflow_body(workflow, options)
    details = f" {reason}" if reason else ""
    return UnsupportedFeature(
        f"{harness.provider}:{harness.surface} cannot execute provider-native "
        f"workflow {workflow.name!r} ({body}). Provider-native script, named, "
        "or file-backed workflows require a surface with native_workflow "
        "support and a registered native adapter. Use portable step workflows "
        "or Workflow.run(...) on this surface."
        f"{details}"
    )


def native_workflow_body(workflow: Workflow, options: WorkflowOptions) -> str:
    """Return a compact human label for the native workflow request."""

    native_input = workflow.native_input()
    if "script" in native_input:
        return "inline script"
    if "scriptPath" in native_input:
        return f"scriptPath={native_input['scriptPath']}"
    if "name" in native_input:
        return f"name={native_input['name']}"
    if options.native:
        return "portable steps requested with native=True"
    return "native workflow"


async def run_step(
    harness: Harness,
    step: Step,
    prompt: str,
    outputs: dict[str, str],
    options: WorkflowOptions,
    *,
    rendered: str | None = None,
) -> StepResult:
    """Run one workflow step."""

    step_harness = harness_for_step(harness, step)
    rendered = (
        rendered if rendered is not None else render_prompt(step, prompt, outputs)
    )
    run = await step_harness.run(rendered, run_options_for_step(step, options))
    return StepResult(
        step=step.name,
        agent=step.agent or "main",
        mode=WorkflowRunMode.YOKE_PORTABLE,
        provider=step_harness.provider,
        surface=step_harness.surface,
        depends_on=tuple(sorted(dependencies_for_step(step))),
        prompt=rendered,
        run=run,
    )


async def run_step_bounded(
    harness: Harness,
    step: Step,
    prompt: object,
    outputs: dict[str, str],
    options: WorkflowOptions,
    rendered: str,
) -> tuple[StepResult, str]:
    """Run one step and normalize its deadline into a failed run."""

    try:
        async with asyncio.timeout(options.step_timeout_seconds):
            result = await run_step(
                harness, step, prompt, outputs, options, rendered=rendered
            )
    except TimeoutError:
        step_harness = harness_for_step(harness, step)
        failure = Failure(message=f"workflow step {step.name!r} timed out")
        run = Run(
            provider=step_harness.provider,
            surface=step_harness.surface,
            status=RunStatus.FAILED,
            output=failure.message,
            failure=failure,
        )
        return (
            StepResult(
                step=step.name,
                agent=step.agent or "main",
                provider=step_harness.provider,
                surface=step_harness.surface,
                depends_on=tuple(sorted(dependencies_for_step(step))),
                prompt=rendered,
                run=run,
            ),
            "step_timed_out",
        )
    return result, "step_completed" if result.run.ok else "step_failed"


async def emit_trace(
    state: WorkflowState,
    options: WorkflowOptions,
    trace: WorkflowTrace,
) -> None:
    """Record a lifecycle trace and notify a sync or async observer."""

    state.traces.append(trace)
    if options.on_event is None:
        return
    try:
        callback_result = options.on_event(trace)
        if inspect.isawaitable(callback_result):
            await callback_result
    except Exception as exc:
        state.traces.append(
            WorkflowTrace(
                kind="observer_failed",
                name=trace.name,
                output=str(exc),
                data={"event_kind": trace.kind},
            )
        )


async def cancel_tasks(tasks) -> None:
    """Cancel and drain workflow tasks without leaking background work."""

    pending = tuple(task for task in tasks if not task.done())
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def ordered_step_names(workflow: Workflow, names: set[str]) -> tuple[str, ...]:
    """Return a set of step names in declaration order."""

    return tuple(step.name for step in workflow.steps if step.name in names)


def step_by_name(workflow: Workflow, name: str) -> Step:
    """Return a declared workflow step by name."""

    return next(step for step in workflow.steps if step.name == name)


def exception_step_result(
    harness: Harness,
    step: Step,
    rendered: str,
    exc: Exception,
) -> StepResult:
    """Normalize an adapter exception into a failed workflow step."""

    step_harness = harness_for_step(harness, step)
    failure = Failure(message=str(exc) or type(exc).__name__, raw=repr(exc))
    return StepResult(
        step=step.name,
        agent=step.agent or "main",
        provider=step_harness.provider,
        surface=step_harness.surface,
        depends_on=tuple(sorted(dependencies_for_step(step))),
        prompt=rendered,
        run=Run(
            provider=step_harness.provider,
            surface=step_harness.surface,
            status=RunStatus.FAILED,
            output=failure.message,
            failure=failure,
        ),
    )


def failed_workflow(
    workflow: Workflow,
    results: list[StepResult],
    output: str,
    failure: Failure | None,
    *,
    harness: Harness,
    traces: list[WorkflowTrace] | None = None,
    failed_step_name: str | None = None,
    interrupted_steps: tuple[str, ...] = (),
) -> WorkflowRun:
    """Return a failed workflow result."""

    return WorkflowRun(
        workflow=workflow.name,
        provider=harness.provider,
        surface=harness.surface,
        status=RunStatus.FAILED,
        steps=tuple(results),
        output=output,
        failure=failure or Failure(message="workflow step failed"),
        traces=tuple(traces or ()),
        failed_step_name=failed_step_name,
        interrupted_steps=interrupted_steps,
    )


def first_failure(results: list[StepResult]) -> Failure | None:
    """Return the first step failure, if any."""

    for result in results:
        if result.run.status != RunStatus.SUCCEEDED:
            return result.run.failure or Failure(
                message=f"workflow step {result.step!r} failed"
            )
    return None


def failed_step_result(results: list[StepResult]) -> StepResult | None:
    """Return the first failed step result, if any."""

    for result in results:
        if result.run.status != RunStatus.SUCCEEDED:
            return result
    return None


def ordered_results(workflow: Workflow, results: list[StepResult]) -> list[StepResult]:
    """Return step results in workflow declaration order."""

    by_step = {result.step: result for result in results}
    return [by_step[step.name] for step in workflow.steps if step.name in by_step]


def validate_workflow_steps(workflow: Workflow) -> None:
    """Reject duplicate step names before scheduling."""

    names: set[str] = set()
    for step in workflow.steps:
        if step.name in names:
            raise ValueError(f"workflow has duplicate step name {step.name!r}")
        names.add(step.name)


def dependencies_for_step(step: Step) -> set[str]:
    """Return explicit and prompt-derived step dependencies."""

    prompt_fields = {
        field
        for _, field, _, _ in Formatter().parse(step.prompt)
        if field and field != "input"
    }
    return {*step.depends_on, *prompt_fields}


def raise_unresolved_dependencies(
    pending: dict[str, Step],
    outputs: dict[str, str],
) -> None:
    """Raise a readable unresolved-dependency error."""

    missing: dict[str, list[str]] = {}
    completed = outputs.keys()
    for step in pending.values():
        unresolved = sorted(dependencies_for_step(step).difference(completed))
        if unresolved:
            missing[step.name] = unresolved
    details = ", ".join(
        f"{step}: {', '.join(names)}" for step, names in missing.items()
    )
    raise ValueError(f"workflow has unresolved dependencies: {details}")


def run_options_for_step(step: Step, options: WorkflowOptions) -> RunOptions:
    """Return run options for one workflow step."""

    run_options = merge_run_options(options.run, step.run)
    output_schema = (
        step.output_schema or run_options.output_schema or options.output_schema
    )
    return run_options.model_copy(update={"output_schema": output_schema})


def merge_run_options(base: RunOptions, override: object | None) -> RunOptions:
    """Overlay a step run option object onto workflow defaults."""

    if override is None:
        return base
    step_options = (
        override
        if isinstance(override, RunOptions)
        else RunOptions.model_validate(override)
    )
    updates = {
        field: getattr(step_options, field)
        for field in step_options.model_fields_set
    }
    return base.model_copy(update=updates)


def workflow_features(
    workflow: Workflow,
    options: WorkflowOptions,
    agent: Agent,
    *,
    provider: object | None = None,
):
    """Return provider features implied by a workflow and every step."""

    features: list[object] = []
    extend_unique(features, options.features(agent.goal, provider=provider))
    if workflow.native:
        extend_unique(features, (Feature.NATIVE_WORKFLOW,))
    for step in workflow.steps:
        step_agent = agent_for_step(agent, step)
        extend_unique(
            features,
            run_options_for_step(step, options).features(
                step_agent.goal,
                provider=provider,
            ),
        )
    return tuple(features)


def agent_for_step(root: Agent, step: Step) -> Agent:
    """Return the declared agent for a step, or the root agent."""

    if step.agent in ("", "main", "root"):
        return root
    return root.subagents.get(step.agent, root)


def extend_unique(items: list[object], values: tuple[object, ...]) -> None:
    """Append values that are not already present."""

    for value in values:
        if value not in items:
            items.append(value)


def harness_for_step(harness: Harness, step: Step) -> Harness:
    """Return the harness used for a workflow step."""

    if step.agent in ("", "main", "root"):
        return harness
    try:
        agent = harness.agent.subagents[step.agent]
    except KeyError as exc:
        raise ValueError(
            f"workflow step {step.name!r} references unknown agent {step.agent!r}"
        ) from exc
    return harness.model_copy(update={"agent": merge_agent(harness.agent, agent)})


def merge_agent(root: Agent, child: Agent) -> Agent:
    """Fill small child-agent gaps from the root agent."""

    return child.model_copy(
        update={
            "model": child.model or root.model,
            "effort": child.effort or root.effort,
        }
    )


def render_prompt(step: Step, prompt: str, outputs: dict[str, str]) -> str:
    """Render a workflow step prompt with simple context."""

    context = {"input": prompt, **outputs}
    try:
        return step.prompt.format(**context)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(
            f"workflow step {step.name!r} prompt references unknown value {missing!r}"
        ) from exc
