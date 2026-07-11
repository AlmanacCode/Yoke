"""Codex app-server adapter.

This surface is intentionally separate from the Codex CLI adapter. The app
server owns thread state, native mutable goals, and the richer notification
stream used by app integrations.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Authentication,
    AuthMethod,
    Event,
    Failure,
    Goal,
    GoalRun,
    Harness,
    Login,
    Model,
    Provider,
    Readiness,
    Run,
    RunStatus,
    Session,
    SessionHistory,
    SessionList,
    SessionMessage,
    SessionSummary,
    Turn,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    CodexAppServerOptions,
    CodexOptions,
    Collaboration,
    ForkOptions,
    GoalLoopOptions,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
)
from yoke.providers.codex_app.events import TurnResult, read_turn, read_turn_step
from yoke.providers.codex_app.fields import as_record, string_field
from yoke.providers.codex_app.goals import app_goal_status, yoke_goal
from yoke.providers.codex_app.policy import (
    approval_policy,
    codex_option,
    network_access,
    sandbox_mode,
    sandbox_policy,
    writable_roots,
)
from yoke.providers.codex_app.process import JsonRpcLineProcess
from yoke.providers.codex_app.prompts import developer_instructions
from yoke.providers.codex_app.rpc import request_rpc
from yoke.providers.codex_app.skills import native_skill_roots
from yoke.readiness import run_command
from yoke.structured import OutputSchema, parse_output, provider_schema
from yoke.surfaces import capabilities_for
from yoke.workflows import native_workflow_unsupported


class CodexAppServer:
    """Adapter for `codex app-server --listen stdio://`."""

    provider: Provider = "codex"
    surface = "codex_app_server"
    capabilities = capabilities_for(provider, surface)

    def __init__(
        self,
        executable: str = "codex",
        *,
        rpc_timeout_seconds: float = 30,
        turn_timeout_seconds: float = 30 * 60,
        ephemeral: bool = False,
        client_name: str = "yoke",
        client_title: str = "Yoke",
        client_version: str = "0.0.0",
        config: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.executable = executable
        self.rpc_timeout_seconds = rpc_timeout_seconds
        self.turn_timeout_seconds = turn_timeout_seconds
        self.ephemeral = ephemeral
        self.client_name = client_name
        self.client_title = client_title
        self.client_version = client_version
        self.config = config or {"mcp_servers": {}}
        self.env = env
        self._threads: dict[str, AppServerThread] = {}
        self._process_refs: dict[int, int] = {}

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        session = await self.start(
            harness,
            SessionOptions(
                model=options.model,
                goal=options.goal,
                inherit_goal=options.inherit_goal,
                effort=options.effort,
                permissions=options.permissions,
                provider=options.provider,
            ),
        )
        try:
            return await self._send(
                session,
                Turn(prompt=prompt),
                options=options,
            )
        finally:
            await self.close(session)

    async def check(self, harness: Harness) -> Readiness:
        try:
            result = await run_command(
                self.executable,
                "login",
                "status",
                env=self.env,
            )
        except FileNotFoundError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex not found on PATH",
                fix=(
                    "Install Codex or pass a Codex app-server adapter with the "
                    "executable path."
                ),
            )
        except TimeoutError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex login status timed out",
            )
        if result.code != 0:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=result.message or f"codex login status exited {result.code}",
                raw=result.stderr or result.stdout,
            )
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=True,
            message=result.message or "codex authenticated",
        )

    async def auth_status(self, harness: Harness) -> Authentication:
        """Distinguish an installed app-server CLI from authentication."""

        readiness = await self.check(harness)
        installed = readiness.message != "codex not found on PATH"
        return Authentication(
            provider=self.provider,
            surface=self.surface,
            methods=(AuthMethod.EXTERNAL,),
            method=AuthMethod.EXTERNAL if readiness.available else None,
            installed=installed,
            authenticated=readiness.available if installed else None,
            compatible=None,
            ready=readiness.available,
            message=readiness.message,
        )

    async def login(
        self,
        harness: Harness,
        method: str,
        *,
        api_key: str | None = None,
    ) -> Login:
        raise UnsupportedFeature(
            "Codex app-server uses existing Codex authentication; run "
            "`codex login` or use the codex_python_sdk surface for "
            "programmatic login."
        )

    async def models(self, harness: Harness) -> tuple[Model, ...]:
        process = await asyncio.to_thread(self._start_process, harness.cwd)
        try:
            return await asyncio.to_thread(self._list_models, process)
        finally:
            await asyncio.to_thread(process.terminate)

    async def workflow(
        self,
        harness: Harness,
        workflow: Workflow,
        prompt: str,
        options: WorkflowOptions,
    ) -> WorkflowRun:
        raise native_workflow_unsupported(
            harness,
            workflow,
            options,
            reason=(
                "Codex app-server has rich thread, event, subagent, and "
                "goal-loop control, but Yoke has not found a documented "
                "provider-native workflow DSL for this surface."
            ),
        )

    async def goal_loop(
        self,
        harness: Harness,
        options: GoalLoopOptions,
    ) -> GoalRun:
        session = await self.start(
            harness,
            SessionOptions(
                goal=options.goal,
                inherit_goal=False,
                channel=options.channel,
            ),
        )
        return GoalRun(
            provider=self.provider,
            surface=self.surface,
            goal=session.goal or options.goal,
            session=session,
            auto_continues=True,
        )

    async def list_sessions(
        self,
        harness: Harness,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        cwd: str | Path | None = None,
        include_worktrees: bool = True,
    ) -> SessionList:
        process = await asyncio.to_thread(self._start_process, harness.cwd)
        try:
            return await asyncio.to_thread(
                self._list_sessions,
                process,
                limit,
                cursor,
                str(cwd) if cwd is not None else None,
            )
        finally:
            await asyncio.to_thread(process.terminate)

    async def read_session(
        self,
        harness: Harness,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        process = await asyncio.to_thread(self._start_process, harness.cwd)
        try:
            return await asyncio.to_thread(
                self._read_session,
                process,
                session_id,
                include_messages,
                limit,
                offset,
            )
        finally:
            await asyncio.to_thread(process.terminate)

    async def rename(self, session: Session, title: str) -> SessionSummary:
        thread = self._threads.get(session.id)
        if thread is not None:
            return await asyncio.to_thread(self._rename_thread, thread, title)
        cwd = session.cwd or Path.cwd()
        process = await asyncio.to_thread(self._start_process, cwd)
        try:
            return await asyncio.to_thread(
                self._rename_session,
                process,
                session.id,
                title,
            )
        finally:
            await asyncio.to_thread(process.terminate)

    async def tag(self, session: Session, tag: str | None) -> SessionSummary:
        raise UnsupportedFeature(
            "Codex app-server does not expose a portable session tag API."
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        permissions = (
            options.permissions or harness.permissions or harness.agent.permissions
        )
        process = await asyncio.to_thread(self._start_process, harness.cwd)
        goal = options.resolve_goal(harness.agent.goal)
        try:
            thread = await asyncio.to_thread(
                self._start_thread,
                process,
                harness,
                options,
                permissions,
                goal,
            )
        except Exception:
            process.terminate()
            raise
        self._threads[thread.thread_id] = thread
        self._retain_process(process)
        session = Session(
            provider=self.provider,
            surface=self.surface,
            id=thread.thread_id,
            provider_session_id=thread.thread_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=None,
            model=options.model or harness.agent.model,
        )
        if goal is not None:
            session = await self.set_goal(session, goal)
        return session

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        return await self._send(session, turn, options=options)

    async def stream(
        self,
        session: Session,
        turn: Turn,
        options: RunOptions,
    ) -> AsyncIterator[Event]:
        thread = self._thread(session)
        result = TurnResult()
        turn_session = session.model_copy(
            update={"permissions": options.permissions or session.permissions}
        )
        turn_id = await asyncio.to_thread(
            self._start_turn,
            thread,
            turn_session,
            turn,
            provider_schema(options.output_schema),
            codex_options_for_run(options),
            options.model or session.model,
        )
        yield Event(
            kind="provider_session",
            surface=self.surface,
            message=f"codex provider session {thread.thread_id}",
            provider_session_id=thread.thread_id,
        )
        deadline = time.monotonic() + self.turn_timeout_seconds
        effective_options = codex_options_for_run(options) or thread.provider_options
        try:
            while True:
                step = await asyncio.to_thread(
                    read_turn_step,
                    thread.process,
                    thread.thread_id,
                    turn_id,
                    result,
                    deadline,
                    codex_request_handler(effective_options),
                )
                for event in step.events:
                    yield event.model_copy(update={"surface": self.surface})
                if step.done:
                    return
        finally:
            thread.active_turn_id = None

    async def get_goal(self, session: Session) -> Goal | None:
        thread = self._thread(session)
        return await asyncio.to_thread(self._get_goal, thread)

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        thread = self._thread(session)
        updated = await asyncio.to_thread(self._set_goal, thread, goal)
        return session.model_copy(update={"goal": updated})

    async def clear_goal(self, session: Session) -> Session:
        thread = self._thread(session)
        await asyncio.to_thread(self._clear_goal, thread)
        return session.model_copy(update={"goal": None})

    async def interrupt(self, session: Session) -> None:
        thread = self._thread(session)
        await asyncio.to_thread(self._interrupt, thread)

    async def compact(self, session: Session) -> None:
        thread = self._thread(session)
        await asyncio.to_thread(self._compact_thread, thread)

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        if session.agent is None or session.cwd is None:
            raise YokeError("Codex app-server fork needs session agent and cwd.")
        source = self._thread(session)
        thread = await asyncio.to_thread(
            self._fork_thread,
            source,
            session,
            options,
        )
        self._threads[thread.thread_id] = thread
        self._retain_process(thread.process)
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=thread.thread_id,
            provider_session_id=thread.thread_id,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions or source.permissions,
            goal=session.goal,
            model=session.model,
        )

    async def close(self, session: Session) -> None:
        thread = self._threads.pop(session.id, None)
        if thread is not None:
            await asyncio.to_thread(self._release_process, thread.process)

    async def _send(
        self,
        session: Session,
        turn: Turn,
        *,
        output_schema: OutputSchema | None = None,
        options: RunOptions | None = None,
    ) -> Run:
        thread = self._thread(session)
        run_options = options or RunOptions(output_schema=output_schema)
        schema = run_options.output_schema or output_schema
        turn_session = session.model_copy(
            update={"permissions": run_options.permissions or session.permissions}
        )
        provider_session_event = Event(
            kind="provider_session",
            surface=self.surface,
            message=f"codex provider session {thread.thread_id}",
            provider_session_id=thread.thread_id,
        )
        if run_options.on_event is not None:
            run_options.on_event(provider_session_event)
        result = await asyncio.to_thread(
            self._run_turn,
            thread,
            turn_session,
            turn,
            provider_schema(schema),
            codex_options_for_run(run_options),
            run_options.model,
            run_options.on_event,
            run_options.timeout_seconds,
        )
        result.events.insert(
            0,
            provider_session_event,
        )
        structured = parse_output(result.output, schema)
        failure = result.failure or structured.failure
        return Run(
            provider=self.provider,
            surface=self.surface,
            status=RunStatus.FAILED if failure else result.status,
            output=result.output,
            data=structured.data,
            events=tuple(
                event.model_copy(update={"surface": self.surface})
                for event in result.events
            ),
            session=session.model_copy(
                update={"provider_session_id": thread.thread_id}
            ),
            usage=result.usage,
            failure=failure,
            requested_model=(
                run_options.model
                or session.model
                or (session.agent.model if session.agent else None)
            ),
        )

    def _thread(self, session: Session) -> AppServerThread:
        try:
            return self._threads[session.id]
        except KeyError as exc:
            raise YokeError(
                f"Codex app-server session is not live: {session.id}"
            ) from exc

    def _start_process(self, cwd: Path) -> JsonRpcLineProcess:
        args = ["app-server"]
        for override in config_overrides(self.config):
            args.extend(["--config", override])
        args.extend(["--listen", "stdio://"])
        return JsonRpcLineProcess.start(self.executable, tuple(args), cwd, self.env)

    def _start_thread(
        self,
        process: JsonRpcLineProcess,
        harness: Harness,
        options: SessionOptions,
        permissions: Any,
        goal: Goal | None,
    ) -> AppServerThread:
        provider_options = codex_options(options)
        app_server_options = codex_app_server_options(provider_options)
        self._initialize(process, provider_options)
        self._configure_skill_roots(process, harness)
        method = "thread/resume" if options.resume else "thread/start"
        params = thread_params(
            harness,
            permissions,
            goal,
            (
                self.ephemeral
                if app_server_options.ephemeral is None
                else app_server_options.ephemeral
            ),
            provider_options,
            options.model or harness.agent.model,
        )
        if options.resume:
            params["threadId"] = options.resume
            params.pop("ephemeral", None)
        response = as_record(
            request_rpc(
                process,
                method,
                params,
                self.rpc_timeout_seconds,
            )
        )
        thread_id = string_field(as_record(response.get("thread")), "id")
        if thread_id is None:
            raise YokeError(f"Codex app-server {method} did not return a thread id")
        return AppServerThread(
            process=process,
            thread_id=thread_id,
            cwd=harness.cwd,
            permissions=permissions,
            effort=options.effort or harness.agent.effort,
            provider_options=provider_options,
            experimental_api=codex_experimental_api(provider_options),
        )

    def _initialize(
        self,
        process: JsonRpcLineProcess,
        options: CodexOptions | dict[str, Any] | None,
    ) -> None:
        request_rpc(
            process,
            "initialize",
            initialize_params(
                name=self.client_name,
                title=self.client_title,
                version=self.client_version,
                capabilities=codex_initialize_capabilities(options),
            ),
            self.rpc_timeout_seconds,
        )

    def _fork_thread(
        self,
        source: AppServerThread,
        session: Session,
        options: ForkOptions,
    ) -> AppServerThread:
        response = as_record(
            request_rpc(
                source.process,
                "thread/fork",
                fork_params(session, options),
                self.rpc_timeout_seconds,
            )
        )
        thread_id = string_field(as_record(response.get("thread")), "id")
        if thread_id is None:
            raise YokeError("Codex app-server thread/fork did not return a thread id")
        return AppServerThread(
            process=source.process,
            thread_id=thread_id,
            cwd=session.cwd or source.cwd,
            permissions=session.permissions or source.permissions,
            effort=source.effort,
            provider_options=source.provider_options,
            experimental_api=source.experimental_api,
        )

    def _retain_process(self, process: JsonRpcLineProcess) -> None:
        key = id(process)
        self._process_refs[key] = self._process_refs.get(key, 0) + 1

    def _release_process(self, process: JsonRpcLineProcess) -> None:
        key = id(process)
        count = self._process_refs.get(key, 0)
        if count <= 1:
            self._process_refs.pop(key, None)
            process.terminate()
            return
        self._process_refs[key] = count - 1

    def _list_models(self, process: JsonRpcLineProcess) -> tuple[Model, ...]:
        self._initialize(process, None)
        response = as_record(
            request_rpc(
                process,
                "model/list",
                {},
                self.rpc_timeout_seconds,
            )
        )
        return parse_models(response)

    def _list_sessions(
        self,
        process: JsonRpcLineProcess,
        limit: int | None,
        cursor: str | None,
        cwd: str | None,
    ) -> SessionList:
        self._initialize(process, None)
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if cwd is not None:
            params["cwd"] = cwd
        response = as_record(
            request_rpc(
                process,
                "thread/list",
                params,
                self.rpc_timeout_seconds,
            )
        )
        return SessionList(
            provider=self.provider,
            surface=self.surface,
            sessions=tuple(
                codex_thread_summary(as_record(thread))
                for thread in response.get("data") or ()
            ),
            next_cursor=string_field(response, "nextCursor"),
            raw=response,
        )

    def _read_session(
        self,
        process: JsonRpcLineProcess,
        session_id: str,
        include_messages: bool,
        limit: int | None,
        offset: int,
    ) -> SessionHistory:
        self._initialize(process, None)
        response = as_record(
            request_rpc(
                process,
                "thread/read",
                {"threadId": session_id, "includeTurns": include_messages},
                self.rpc_timeout_seconds,
            )
        )
        thread = as_record(response.get("thread"))
        turns = tuple(as_record(turn) for turn in (thread.get("turns") or ()))
        if offset:
            turns = turns[offset:]
        if limit is not None:
            turns = turns[:limit]
        return SessionHistory(
            provider=self.provider,
            surface=self.surface,
            session=codex_thread_summary(thread),
            messages=tuple(codex_thread_message(session_id, turn) for turn in turns)
            if include_messages
            else (),
            raw=response,
        )

    def _rename_thread(self, thread: AppServerThread, title: str) -> SessionSummary:
        return self._rename_session(
            thread.process,
            thread.thread_id,
            title,
            initialize=False,
        )

    def _rename_session(
        self,
        process: JsonRpcLineProcess,
        session_id: str,
        title: str,
        *,
        initialize: bool = True,
    ) -> SessionSummary:
        if initialize:
            self._initialize(process, None)
        response = as_record(
            request_rpc(
                process,
                "thread/name/set",
                {"threadId": session_id, "name": title},
                self.rpc_timeout_seconds,
            )
        )
        thread = as_record(response.get("thread"))
        if not thread:
            thread = {"id": session_id, "name": title}
        return codex_thread_summary(thread)

    def _configure_skill_roots(
        self,
        process: JsonRpcLineProcess,
        harness: Harness,
    ) -> None:
        skill_roots = native_skill_roots(harness.agent)
        if skill_roots:
            request_rpc(
                process,
                "skills/extraRoots/set",
                {"extraRoots": [str(root) for root in skill_roots]},
                self.rpc_timeout_seconds,
            )

    def _run_turn(
        self,
        thread: AppServerThread,
        session: Session,
        turn: Turn,
        output_schema: dict[str, Any] | None,
        provider_options: CodexOptions | dict[str, Any] | None,
        model: str | None = None,
        on_event: Callable[[Event], None] | None = None,
        timeout_seconds: float | None = None,
    ) -> TurnResult:
        turn_id = self._start_turn(
            thread,
            session,
            turn,
            output_schema,
            provider_options=provider_options,
            model=model,
        )
        effective_timeout = timeout_seconds or self.turn_timeout_seconds
        try:
            try:
                return read_turn(
                    thread.process,
                    thread.thread_id,
                    turn_id,
                    effective_timeout,
                    codex_request_handler(provider_options or thread.provider_options),
                    (
                        None
                        if on_event is None
                        else lambda event: on_event(
                            event.model_copy(update={"surface": self.surface})
                        )
                    ),
                )
            except TimeoutError:
                try:
                    self._interrupt(thread)
                except Exception:
                    pass
                return TurnResult(
                    status=RunStatus.FAILED,
                    failure=Failure(
                        message=(
                            "Codex app-server run timed out after "
                            f"{effective_timeout:g} seconds"
                        ),
                        code="timeout",
                    ),
                )
        finally:
            thread.active_turn_id = None

    def _start_turn(
        self,
        thread: AppServerThread,
        session: Session,
        turn: Turn,
        output_schema: dict[str, Any] | None,
        provider_options: CodexOptions | dict[str, Any] | None,
        model: str | None = None,
    ) -> str | None:
        require_experimental_api(thread, provider_options)
        response = as_record(
            request_rpc(
                thread.process,
                "turn/start",
                turn_params(
                    thread,
                    session,
                    turn,
                    output_schema,
                    provider_options=provider_options,
                    model=model,
                ),
                self.rpc_timeout_seconds,
            )
        )
        turn_id = string_field(as_record(response.get("turn")), "id")
        thread.active_turn_id = turn_id
        return turn_id

    def _set_goal(self, thread: AppServerThread, goal: Goal) -> Goal:
        response = as_record(
            request_rpc(
                thread.process,
                "thread/goal/set",
                {
                    "threadId": thread.thread_id,
                    "objective": goal.objective,
                    "status": app_goal_status(goal.status),
                    "tokenBudget": goal.token_budget,
                },
                self.rpc_timeout_seconds,
            )
        )
        return yoke_goal(as_record(response.get("goal"))) or goal

    def _get_goal(self, thread: AppServerThread) -> Goal | None:
        response = as_record(
            request_rpc(
                thread.process,
                "thread/goal/get",
                {"threadId": thread.thread_id},
                self.rpc_timeout_seconds,
            )
        )
        return yoke_goal(as_record(response.get("goal")))

    def _clear_goal(self, thread: AppServerThread) -> None:
        request_rpc(
            thread.process,
            "thread/goal/clear",
            {"threadId": thread.thread_id},
            self.rpc_timeout_seconds,
        )

    def _interrupt(self, thread: AppServerThread) -> None:
        if thread.active_turn_id is None:
            raise YokeError("Codex app-server session has no active turn to interrupt.")
        request_rpc(
            thread.process,
            "turn/interrupt",
            {"threadId": thread.thread_id, "turnId": thread.active_turn_id},
            self.rpc_timeout_seconds,
        )

    def _compact_thread(self, thread: AppServerThread) -> None:
        request_rpc(
            thread.process,
            "thread/compact/start",
            {"threadId": thread.thread_id},
            self.rpc_timeout_seconds,
        )


@dataclass
class AppServerThread:
    process: JsonRpcLineProcess
    thread_id: str
    cwd: Path
    permissions: Any
    effort: Any | None
    provider_options: CodexOptions | dict[str, Any]
    experimental_api: bool = False
    active_turn_id: str | None = None


def initialize_params(
    *,
    name: str,
    title: str,
    version: str,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "clientInfo": {
            "name": name,
            "title": title,
            "version": version,
        }
    }
    if capabilities:
        params["capabilities"] = capabilities
    return params


def config_overrides(config: dict[str, Any]) -> list[str]:
    overrides: list[str] = []
    flatten_config(config, "", overrides)
    return overrides


def flatten_config(value: Any, prefix: str, overrides: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flatten_config(child, path, overrides)
        return
    if not prefix:
        raise ValueError("Codex app-server config overrides must be keyed")
    overrides.append(f"{prefix}={json.dumps(value)}")


def thread_params(
    harness: Harness,
    permissions: Any,
    goal: Goal | None,
    ephemeral: bool,
    provider_options: CodexOptions | dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    permission_profile = codex_app_server_option(provider_options, "permissions")
    params: dict[str, Any] = {
        "cwd": str(harness.cwd),
        "model": model or harness.agent.model,
        "approvalPolicy": approval_policy(permissions, provider_options),
        "developerInstructions": developer_instructions(harness.agent),
        "ephemeral": ephemeral if goal is None else False,
    }
    if permission_profile is not None:
        params["permissions"] = permission_profile
    else:
        params["sandbox"] = sandbox_mode(permissions, provider_options)
    add_app_server_options(
        params,
        provider_options,
        fields=(
            "approvals_reviewer",
            "runtime_workspace_roots",
            "environments",
            "selected_capability_roots",
            "allow_provider_model_fallback",
            "service_tier",
        ),
    )
    return params


def fork_params(session: Session, options: ForkOptions) -> dict[str, Any]:
    params: dict[str, Any] = {
        "threadId": session.id,
        "ephemeral": options.ephemeral,
    }
    if options.last_turn_id is not None:
        params["lastTurnId"] = options.last_turn_id
    if options.exclude_turns is not None:
        params["excludeTurns"] = options.exclude_turns
    return params


def turn_params(
    thread: AppServerThread,
    session: Session,
    turn: Turn,
    output_schema: dict[str, Any] | None,
    *,
    provider_options: CodexOptions | dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    permissions = session.permissions or thread.permissions
    effective_options = (
        thread.provider_options if provider_options is None else provider_options
    )
    permission_profile = codex_app_server_option(effective_options, "permissions")
    params: dict[str, Any] = {
        "threadId": thread.thread_id,
        "cwd": str(thread.cwd),
        "input": [
            {
                "type": "text",
                "text": turn.prompt,
                "text_elements": [],
            }
        ],
        "approvalPolicy": approval_policy(permissions, effective_options),
        "model": model
        or turn.model
        or session.model
        or (session.agent.model if session.agent else None),
        "effort": str(thread.effort) if thread.effort else None,
        "outputSchema": output_schema,
    }
    if permission_profile is not None:
        params["permissions"] = permission_profile
    else:
        params["sandboxPolicy"] = sandbox_policy(
            thread.cwd,
            sandbox_mode(permissions, effective_options),
            network=network_access(permissions, effective_options),
            writable_roots=writable_roots(effective_options),
        )
    collaboration_mode = codex_collaboration_mode(effective_options)
    if collaboration_mode is not None:
        params["collaborationMode"] = collaboration_mode
    add_app_server_options(
        params,
        effective_options,
        fields=(
            "approvals_reviewer",
            "runtime_workspace_roots",
            "environments",
            "service_tier",
            "client_user_message_id",
        ),
    )
    return params


def codex_options(options: SessionOptions) -> CodexOptions | dict[str, Any]:
    if options.provider is None:
        return {}
    return options.provider.codex


def codex_options_for_run(options: RunOptions) -> CodexOptions | dict[str, Any] | None:
    if options.provider is None:
        return None
    return options.provider.codex


def codex_experimental_api(options: CodexOptions | dict[str, Any] | None) -> bool:
    if options is None:
        return False
    if isinstance(options, CodexOptions):
        if options.experimental_api:
            return True
        if options.has_app_server_experimental_fields():
            return True
        return raw_experimental_api(options.raw)
    if options.get("experimental_api") is True:
        return True
    if options.get("experimentalApi") is True:
        return True
    if raw_app_server_experimental_fields(options):
        return True
    raw = options.get("raw")
    if isinstance(raw, dict):
        return raw_experimental_api(raw) or raw_app_server_experimental_fields(raw)
    return False


def codex_app_server_options(
    options: CodexOptions | dict[str, Any] | None,
) -> CodexAppServerOptions:
    if isinstance(options, CodexOptions):
        value = options.app_server
        if isinstance(value, CodexAppServerOptions):
            return value
        if isinstance(value, dict):
            return CodexAppServerOptions.model_validate(value)
        raw_value = options.raw.get("app_server", options.raw.get("appServer"))
        if isinstance(raw_value, dict):
            return CodexAppServerOptions.model_validate(raw_value)
        return CodexAppServerOptions()
    if isinstance(options, dict):
        value = options.get("app_server", options.get("appServer"))
        if isinstance(value, dict):
            return CodexAppServerOptions.model_validate(value)
        raw = options.get("raw")
        if isinstance(raw, dict):
            return codex_app_server_options(raw)
    return CodexAppServerOptions()


def codex_initialize_capabilities(
    options: CodexOptions | dict[str, Any] | None,
) -> dict[str, Any]:
    return codex_app_server_options(options).capabilities(
        experimental_api=codex_experimental_api(options)
    )


def codex_request_handler(
    options: CodexOptions | dict[str, Any] | None,
) -> Any | None:
    app_server = codex_app_server_options(options)
    return app_server.request_handler or app_server.policy


def raw_experimental_api(options: dict[str, Any]) -> bool:
    if options.get("experimental_api") is True:
        return True
    return options.get("experimentalApi") is True


def raw_app_server_experimental_fields(options: dict[str, Any]) -> bool:
    """Return whether raw dict options include experimental app-server fields."""

    keys = {
        "permissions",
        "permission_profile",
        "permissionProfile",
        "runtime_workspace_roots",
        "runtimeWorkspaceRoots",
        "environments",
        "selected_capability_roots",
        "selectedCapabilityRoots",
        "allow_provider_model_fallback",
        "allowProviderModelFallback",
    }
    return any(options.get(key) is not None for key in keys)


def require_experimental_api(
    thread: AppServerThread,
    provider_options: CodexOptions | dict[str, Any] | None,
) -> None:
    if codex_experimental_api(provider_options) and not thread.experimental_api:
        raise YokeError(
            "Codex app-server session was initialized without experimentalApi; "
            "start the session with CodexOptions(experimental_api=True)."
        )


def codex_collaboration_mode(
    options: CodexOptions | dict[str, Any],
) -> dict[str, Any] | None:
    if isinstance(options, CodexOptions):
        value = options.collaboration
        if isinstance(value, Collaboration):
            return value.wire()
        if isinstance(value, dict):
            return value
        raw_value = options.raw.get(
            "collaboration_mode",
            options.raw.get("collaborationMode"),
        )
        return raw_value if isinstance(raw_value, dict) else None
    value = options.get("collaboration_mode", options.get("collaborationMode"))
    return value if isinstance(value, dict) else None


def add_app_server_options(
    params: dict[str, Any],
    options: CodexOptions | dict[str, Any] | None,
    *,
    fields: tuple[str, ...],
) -> None:
    """Add typed Codex app-server thread/turn fields to JSON-RPC params."""

    for field in fields:
        value = codex_app_server_option(options, field)
        if value is not None:
            params[codex_app_server_wire_key(field)] = value


def codex_app_server_option(
    options: CodexOptions | dict[str, Any] | None,
    field: str,
) -> Any | None:
    """Return one app-server option from typed fields or raw dicts."""

    value = codex_option(options, field)
    if value is None:
        return None
    if field in {
        "runtime_workspace_roots",
        "environments",
        "selected_capability_roots",
    }:
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, list):
            return value
    return value


def codex_app_server_wire_key(field: str) -> str:
    """Return the app-server JSON-RPC spelling for a Codex option field."""

    return {
        "approvals_reviewer": "approvalsReviewer",
        "runtime_workspace_roots": "runtimeWorkspaceRoots",
        "selected_capability_roots": "selectedCapabilityRoots",
        "allow_provider_model_fallback": "allowProviderModelFallback",
        "service_tier": "serviceTier",
        "client_user_message_id": "clientUserMessageId",
    }.get(field, field)


def parse_models(response: dict[str, Any]) -> tuple[Model, ...]:
    """Parse app-server model/list response into Yoke models."""

    value = response.get("models", response.get("data", ()))
    if not isinstance(value, list):
        return ()
    return tuple(model for item in value if (model := parse_model(item)) is not None)


def parse_model(value: Any) -> Model | None:
    if not isinstance(value, dict):
        return None
    model_id = string_field(value, "id") or string_field(value, "name")
    if model_id is None:
        return None
    efforts = value.get("supportedReasoningEfforts")
    return Model(
        id=model_id,
        hidden=value.get("hidden") is True,
        reasoning_efforts=reasoning_efforts(efforts),
        raw=value,
    )


def codex_thread_summary(thread: dict[str, Any]) -> SessionSummary:
    thread_id = string_field(thread, "id") or ""
    return SessionSummary(
        provider="codex",
        surface="codex_app_server",
        id=thread_id,
        provider_session_id=string_field(thread, "sessionId") or thread_id,
        title=string_field(thread, "name"),
        summary=string_field(thread, "preview"),
        cwd=string_field(thread, "cwd"),
        created_at=int_field(thread, "createdAt"),
        updated_at=int_field(thread, "updatedAt"),
        raw=thread,
    )


def codex_thread_message(session_id: str, turn: dict[str, Any]) -> SessionMessage:
    return SessionMessage(
        provider="codex",
        surface="codex_app_server",
        session_id=session_id,
        id=string_field(turn, "id") or string_field(turn, "turnId"),
        role=string_field(turn, "role") or string_field(turn, "type") or "turn",
        content=turn.get("items") or turn.get("preview"),
        raw=turn,
    )


def int_field(record: dict[str, Any], key: str) -> int | None:
    value = record.get(key)
    return value if isinstance(value, int) else None


def reasoning_efforts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    efforts: list[str] = []
    for item in value:
        if isinstance(item, str):
            efforts.append(item)
        elif isinstance(item, dict):
            effort = string_field(item, "reasoningEffort") or string_field(item, "id")
            if effort is not None:
                efforts.append(effort)
    return tuple(efforts)
