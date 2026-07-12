"""OpenCode provider adapter.

OpenCode has no Python SDK. This surface spawns `opencode serve --port 0` as
a child process and drives it over HTTP. Following the precedent set by
`CodexAppServer` (providers/codex_app/process.py), the process/HTTP/DB-
polling mechanics stay synchronous and thread-backed, and this adapter's
async `ProviderAdapter` methods bridge to them via `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Approval,
    Event,
    EventKind,
    Goal,
    GoalRun,
    Harness,
    Login,
    Model,
    Permissions,
    Provider,
    Readiness,
    Response,
    Run,
    RunStatus,
    Session,
    SessionHistory,
    SessionList,
    SessionMessage,
    SessionSummary,
    Surface,
    Turn,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    ForkOptions,
    GoalLoopOptions,
    OpencodeOptions,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
    opencode_request_handler,
)
from yoke.providers.opencode import http
from yoke.providers.opencode.db import query_readonly_or_empty
from yoke.providers.opencode.failures import classify_opencode_failure
from yoke.providers.opencode.fields import JsonObject, as_record, string_field
from yoke.providers.opencode.hooks import (
    OPENCODE_HOOK_PLUGIN_SOURCE,
    OpencodeHookBridge,
)
from yoke.providers.opencode.hooks import resolve as resolve_hook_request
from yoke.providers.opencode.parts import final_text_from_parts
from yoke.providers.opencode.permissions import OpencodePermissionWatchdog
from yoke.providers.opencode.process import (
    OpencodeServerProcess,
    OpencodeServerStartupError,
    start_opencode_server,
)
from yoke.providers.opencode.progress import (
    OPENCODE_POLL_INTERVAL_SECONDS,
    OPENCODE_STUCK_TOOL_CALL_SECONDS,
    OpencodeProgressWatchdog,
    OpencodeStuckToolCallError,
)
from yoke.providers.opencode.usage import parse_opencode_usage
from yoke.providers.runtime_deployment import RuntimeDeployment, deploy_runtime
from yoke.surfaces import capabilities_for
from yoke.workflows import native_workflow_unsupported

OPENCODE_COMMAND = "opencode"
OPENCODE_MODEL_SEPARATOR = "/"
OPENCODE_CHECK_STARTUP_TIMEOUT_SECONDS = 5.0
OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS = 5.0
OPENCODE_RUN_STARTUP_TIMEOUT_SECONDS = 10.0
OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS = 900.0
OPENCODE_NOT_INSTALLED_MESSAGE = "opencode not found on PATH"
OPENCODE_SERVER_REPAIR = "run `opencode serve` directly to check for a startup error"
OPENCODE_PROVIDER_REPAIR = (
    "sign in with `opencode auth login` or configure a provider API key"
)
# How long the main thread waits between checks of the watchdog's
# stuck_reason while the sender thread is still alive.
OPENCODE_STUCK_CHECK_INTERVAL_SECONDS = 1.0


def split_opencode_model(model: str) -> tuple[str, str]:
    provider_id, separator, model_id = model.partition(OPENCODE_MODEL_SEPARATOR)
    if separator == "" or provider_id == "" or model_id == "":
        raise ValueError(f'opencode model must be "provider/model", got: {model!r}')
    return provider_id, model_id


@dataclass
class _OpencodeSession:
    process: OpencodeServerProcess
    session_id: str
    cwd: Path
    environment: dict[str, str] | None
    db_path: Path
    # Persist across turns so a later send() doesn't re-poll and re-emit an
    # earlier turn's already-seen parts through on_event.
    known_sessions: set[str] = field(default_factory=set)
    seen_part_ids: set[str] = field(default_factory=set)
    # Persisted the same way as seen_part_ids, so a permission answered on an
    # earlier turn isn't rediscovered and re-resolved on a later one.
    seen_permission_ids: set[str] = field(default_factory=set)
    # OpenCode's session/message API has no dedicated system-prompt field
    # (unlike Claude's system_prompt or Codex app-server's developer
    # instructions) — Agent.instructions is prepended to the first turn's
    # prompt text instead. Without this, the model receives only the bare
    # task prompt and never learns what it's actually supposed to do.
    instructions: str | None = None
    instructions_sent: bool = False
    # Session-level provider.opencode options (mirrors CodexAppServer's
    # thread.provider_options): a later turn's RunOptions.provider.opencode
    # overrides this, but falls back here when a turn doesn't set one.
    provider_options: OpencodeOptions | dict[str, object] | None = None
    # Set for the duration of one _send() call so a live tool.execute.before
    # hook (OpencodeHookBridge — a long-lived, process-scoped server that
    # outlives any one turn) can still emit its resolved event into whatever
    # turn is currently in flight. None between turns and while idle.
    current_emit: Callable[[Event], None] | None = None


class OpencodeServer:
    """Adapter for `opencode serve --port 0`."""

    provider: Provider = "opencode"
    surface = "opencode_server"
    capabilities = capabilities_for(provider, surface)

    def __init__(
        self,
        command: str = OPENCODE_COMMAND,
        *,
        db_path: Path | None = None,
        poll_interval_seconds: float = OPENCODE_POLL_INTERVAL_SECONDS,
        stuck_after_seconds: float = OPENCODE_STUCK_TOOL_CALL_SECONDS,
    ) -> None:
        self.command = command
        self._db_path_override = db_path
        self.poll_interval_seconds = poll_interval_seconds
        self.stuck_after_seconds = stuck_after_seconds
        self._sessions: dict[str, _OpencodeSession] = {}
        # A forked session shares its parent's server process (fork() opens
        # a new session id on the same running `opencode serve` instance,
        # not a new process), so termination is reference-counted rather
        # than tied to any one session — mirrors CodexAppServer's
        # _retain_process/_release_process.
        self._process_refs: dict[int, int] = {}
        # Keyed by id(process), not by session: a fork shares its parent's
        # runtime deployment (skills dir, OPENCODE_CONFIG_DIR), so cleanup
        # must wait for the last session referencing that process to close,
        # not whichever session happens to close first. Mirrors
        # CodexAppServer's own _deployments keyed by id(process).
        self._deployments: dict[int, RuntimeDeployment] = {}
        # Same id(process) keying as _deployments: one bridge per process,
        # shared across forks, torn down alongside the deployment.
        self._hook_bridges: dict[int, OpencodeHookBridge] = {}

    async def check(self, harness: Harness) -> Readiness:
        return await asyncio.to_thread(self._check, harness.cwd, harness.environment)

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        # Regression: provider (needed to deploy the tool-hook bridge —
        # OpencodeHookBridge only ever reads session-creation-time options,
        # see _maybe_deploy_hook_bridge) was dropped here, matching neither
        # CodexAppServer.run() nor this adapter's own per-turn permission
        # resolution, which does see RunOptions.provider via
        # opencode_options_for_run() in _send().
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
            return await self.send(session, Turn(prompt=prompt), options)
        finally:
            await self.close(session)

    async def models(self, harness: Harness) -> tuple[Model, ...]:
        return await asyncio.to_thread(self._models, harness.cwd, harness.environment)

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
            reason="OpenCode has no documented native workflow DSL.",
        )

    async def goal_loop(self, harness: Harness, options: GoalLoopOptions) -> GoalRun:
        raise UnsupportedFeature("OpenCode has no goal-loop concept.")

    async def get_goal(self, session: Session) -> Goal | None:
        raise UnsupportedFeature("OpenCode has no goal concept.")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("OpenCode has no goal concept.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("OpenCode has no goal concept.")

    async def login(
        self,
        harness: Harness,
        method: str,
        *,
        api_key: str | None = None,
    ) -> Login:
        if method != "api_key" or api_key is None:
            raise UnsupportedFeature(
                "OpenCode adapter only wires api_key login (PUT /auth/:id); "
                "OAuth authorize/callback exists in the API but is not wired "
                "in this adapter yet."
            )
        provider_id = (
            harness.agent.model.split(OPENCODE_MODEL_SEPARATOR, 1)[0]
            if (harness.agent.model and OPENCODE_MODEL_SEPARATOR in harness.agent.model)
            else None
        )
        if provider_id is None:
            raise UnsupportedFeature(
                "api_key login needs a provider id; set Harness.agent.model to "
                '"provider/model" first.'
            )
        await asyncio.to_thread(
            self._login, harness.cwd, harness.environment, provider_id, api_key
        )
        return Login(
            provider=self.provider,
            surface=self.surface,
            method="api_key",
            success=True,
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
        sessions = await asyncio.to_thread(
            self._list_sessions, harness.cwd, harness.environment, limit
        )
        return SessionList(
            provider=self.provider, surface=self.surface, sessions=sessions
        )

    async def read_session(
        self,
        harness: Harness,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        return await asyncio.to_thread(
            self._read_session,
            harness.cwd,
            harness.environment,
            session_id,
            include_messages,
        )

    async def rename(self, session: Session, title: str) -> SessionSummary:
        internal = self._require_internal(session)
        record = await asyncio.to_thread(
            http.rename_session,
            internal.process.base_url,
            internal.session_id,
            title,
            OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS,
        )
        return _session_summary(record, self.provider, self.surface)

    async def tag(self, session: Session, tag: str | None) -> SessionSummary:
        raise UnsupportedFeature("OpenCode does not expose a session tag API.")

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        internal = self._require_internal(session)
        record = await asyncio.to_thread(
            http.fork_session,
            internal.process.base_url,
            internal.session_id,
            OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS,
            message_id=options.last_turn_id,
        )
        forked_id = string_field(record, "id")
        if forked_id is None:
            raise YokeError("opencode fork did not return a session id")
        forked = _OpencodeSession(
            process=internal.process,
            session_id=forked_id,
            cwd=internal.cwd,
            environment=internal.environment,
            db_path=internal.db_path,
            # A fork already carries the parent conversation's context
            # server-side, so re-sending instructions on the fork's first
            # turn would be redundant — mark instructions_sent=True rather
            # than leaving instructions=None, which would look like they
            # were never sent at all and isn't the intent here.
            instructions=internal.instructions,
            instructions_sent=True,
            # Same reasoning as instructions: a fork should keep answering
            # permissions the way the parent session was configured to,
            # not silently fall back to "no handler configured" default-deny.
            provider_options=internal.provider_options,
        )
        self._retain_process(internal.process)
        self._sessions[forked_id] = forked
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=forked_id,
            provider_session_id=forked_id,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions,
            model=session.model,
        )

    async def interrupt(self, session: Session) -> None:
        internal = self._require_internal(session)
        await asyncio.to_thread(
            http.abort_session,
            internal.process.base_url,
            internal.session_id,
            OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS,
        )

    async def compact(self, session: Session) -> None:
        internal = self._require_internal(session)
        if session.model is None:
            raise YokeError("opencode compact needs a session model to summarize with.")
        provider_id, model_id = split_opencode_model(session.model)
        await asyncio.to_thread(
            http.summarize_session,
            internal.process.base_url,
            internal.session_id,
            provider_id,
            model_id,
            OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS,
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        deployment = deploy_runtime(
            harness.agent, Provider.OPENCODE, harness.runtime_root
        )
        try:
            internal = await asyncio.to_thread(
                self._start_session, harness, options, deployment
            )
        except Exception:
            deployment.cleanup()
            raise
        self._retain_process(internal.process)
        self._deployments[id(internal.process)] = deployment
        self._sessions[internal.session_id] = internal
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=internal.session_id,
            provider_session_id=internal.session_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=_resolved_permissions(harness, options),
            model=options.model or harness.agent.model,
            runtime_root=harness.runtime_root,
        )

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        internal = self._require_internal(session)
        model = options.model or turn.model or session.model
        if model is None:
            raise YokeError('opencode send needs a model ("provider/model").')
        return await asyncio.to_thread(self._send, internal, turn, model, options)

    async def stream(
        self,
        session: Session,
        turn: Turn,
        options: RunOptions,
    ) -> AsyncIterator[Event]:
        internal = self._require_internal(session)
        model = options.model or turn.model or session.model
        if model is None:
            raise YokeError('opencode stream needs a model ("provider/model").')
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        user_on_event = options.on_event

        def relay(event: Event) -> None:
            if user_on_event is not None:
                user_on_event(event)
            loop.call_soon_threadsafe(queue.put_nowait, event)

        # _send already emits every event through options.on_event as it
        # happens (the DB-poll watchdog calls it live, turn by turn), so
        # streaming just needs to relay those same events onto an asyncio
        # queue instead of collecting them into a Run — no separate
        # streaming implementation to keep in sync with _send's logic.
        streaming_options = options.model_copy(update={"on_event": relay})
        send_task = asyncio.ensure_future(
            asyncio.to_thread(self._send, internal, turn, model, streaming_options)
        )
        send_task.add_done_callback(
            lambda _task: loop.call_soon_threadsafe(queue.put_nowait, None)
        )
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            run = await send_task
        if run.status == RunStatus.FAILED:
            message = run.failure.message if run.failure is not None else run.output
            raise YokeError(message)

    async def close(self, session: Session) -> None:
        internal = self._sessions.pop(session.id, None)
        if internal is None:
            return
        await asyncio.to_thread(self._release_process, internal.process)

    # -- synchronous internals, bridged via asyncio.to_thread above --

    def _require_internal(self, session: Session) -> _OpencodeSession:
        internal = self._sessions.get(session.id)
        if internal is None:
            raise YokeError(f"no live opencode session for {session.id!r}")
        return internal

    def _retain_process(self, process: OpencodeServerProcess) -> None:
        key = id(process)
        self._process_refs[key] = self._process_refs.get(key, 0) + 1

    def _release_process(self, process: OpencodeServerProcess) -> None:
        key = id(process)
        count = self._process_refs.get(key, 0)
        if count <= 1:
            self._process_refs.pop(key, None)
            process.terminate()
            deployment = self._deployments.pop(key, None)
            if deployment is not None:
                deployment.cleanup()
            bridge = self._hook_bridges.pop(key, None)
            if bridge is not None:
                bridge.stop()
            return
        self._process_refs[key] = count - 1

    def _check(self, cwd: Path, environment: dict[str, str]) -> Readiness:
        try:
            with self._brief_server(cwd, environment) as server:
                providers = http.get_providers(
                    server.base_url, OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS
                )
        except FileNotFoundError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=OPENCODE_NOT_INSTALLED_MESSAGE,
                fix="Install OpenCode: npm install -g opencode-ai",
            )
        except OpencodeServerStartupError as error:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=str(error),
                fix=OPENCODE_SERVER_REPAIR,
            )
        if len(providers) == 0:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="no opencode providers are configured",
                fix=OPENCODE_PROVIDER_REPAIR,
            )
        names = ", ".join(
            string_field(item, "name") or string_field(item, "id") or "provider"
            for item in providers
        )
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=True,
            message=f"opencode providers configured: {names}",
        )

    def _models(self, cwd: Path, environment: dict[str, str]) -> tuple[Model, ...]:
        with self._brief_server(cwd, environment) as server:
            providers = http.get_providers(
                server.base_url, OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS
            )
        models: list[Model] = []
        for provider in providers:
            provider_id = string_field(provider, "id")
            if provider_id is None:
                continue
            entries = provider.get("models")
            model_ids = _model_ids(entries)
            for model_id in model_ids:
                models.append(Model(id=f"{provider_id}/{model_id}", raw=provider))
        return tuple(models)

    def _brief_server(self, cwd: Path, environment: dict[str, str]):
        return start_opencode_server(
            self.command,
            cwd,
            OPENCODE_CHECK_STARTUP_TIMEOUT_SECONDS,
            env=environment,
        )

    def _login(
        self,
        cwd: Path,
        environment: dict[str, str],
        provider_id: str,
        api_key: str,
    ) -> None:
        server = start_opencode_server(
            self.command,
            cwd,
            OPENCODE_CHECK_STARTUP_TIMEOUT_SECONDS,
            env=environment,
        )
        try:
            http.set_auth(
                server.base_url,
                provider_id,
                api_key,
                OPENCODE_CHECK_REQUEST_TIMEOUT_SECONDS,
            )
        finally:
            server.terminate()

    def _list_sessions(
        self,
        cwd: Path,
        environment: dict[str, str],
        limit: int | None,
    ) -> tuple[SessionSummary, ...]:
        server = start_opencode_server(
            self.command,
            cwd,
            OPENCODE_RUN_STARTUP_TIMEOUT_SECONDS,
            env=environment,
        )
        try:
            records = http.list_sessions(
                server.base_url, OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS
            )
        finally:
            server.terminate()
        if limit is not None:
            records = records[:limit]
        return tuple(
            _session_summary(record, self.provider, self.surface) for record in records
        )

    def _read_session(
        self,
        cwd: Path,
        environment: dict[str, str],
        session_id: str,
        include_messages: bool,
    ) -> SessionHistory:
        server = start_opencode_server(
            self.command,
            cwd,
            OPENCODE_RUN_STARTUP_TIMEOUT_SECONDS,
            env=environment,
        )
        try:
            record = http.read_session(
                server.base_url, session_id, OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS
            )
        finally:
            server.terminate()
        summary = _session_summary(record, self.provider, self.surface)
        messages: tuple[SessionMessage, ...] = ()
        if include_messages:
            db_path = self._resolve_db_path()
            rows = query_readonly_or_empty(
                db_path,
                "SELECT message.id AS id, message.data AS message_data "
                "FROM message WHERE message.session_id = ? "
                "ORDER BY message.time_created",
                (session_id,),
            )
            messages = tuple(
                SessionMessage(
                    provider=self.provider,
                    surface=self.surface,
                    session_id=session_id,
                    id=row["id"],
                    raw=row["message_data"],
                )
                for row in rows
            )
        return SessionHistory(
            provider=self.provider,
            surface=self.surface,
            session=summary,
            messages=messages,
        )

    def _start_session(
        self,
        harness: Harness,
        options: SessionOptions,
        deployment: RuntimeDeployment,
    ) -> _OpencodeSession:
        environment = dict(harness.environment)
        # May set deployment.opencode_config_dir for the first time (no
        # skills/agents/MCP configured, only hooks) — run before the
        # OPENCODE_CONFIG_DIR check below so it's picked up either way.
        hook_bridge = self._maybe_deploy_hook_bridge(options, deployment)
        if deployment.opencode_config_dir is not None:
            environment["OPENCODE_CONFIG_DIR"] = str(deployment.opencode_config_dir)
        if deployment.opencode_config_content is not None:
            environment["OPENCODE_CONFIG_CONTENT"] = deployment.opencode_config_content
        if hook_bridge is not None:
            environment["YOKE_HOOK_BRIDGE_URL"] = hook_bridge.base_url
        server = start_opencode_server(
            self.command,
            harness.cwd,
            OPENCODE_RUN_STARTUP_TIMEOUT_SECONDS,
            env=environment,
        )
        try:
            record = http.create_session(
                server.base_url,
                str(harness.cwd),
                harness.agent.description or "yoke run",
                OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS,
                permission=_session_permission_block(
                    _resolved_permissions(harness, options)
                ),
            )
            session_id = string_field(record, "id")
            if session_id is None:
                raise OpencodeServerStartupError("opencode did not return a session id")
        except Exception:
            server.terminate()
            if hook_bridge is not None:
                hook_bridge.stop()
            raise
        if hook_bridge is not None:
            self._hook_bridges[id(server)] = hook_bridge
        return _OpencodeSession(
            process=server,
            session_id=session_id,
            cwd=harness.cwd,
            environment=environment or None,
            db_path=self._resolve_db_path(),
            instructions=harness.agent.instructions,
            provider_options=opencode_options(options),
        )

    def _maybe_deploy_hook_bridge(
        self,
        options: SessionOptions,
        deployment: RuntimeDeployment,
    ) -> OpencodeHookBridge | None:
        """Deploy the tool.execute.before hook plugin, only if opted into.

        No caller-configured request_handler/policy means no plugin file
        and no bridge server — zero overhead for sessions that don't use
        hooks, matching how MCP/skills/agents only ever write files a
        caller's Agent actually asked for.
        """

        handler = opencode_request_handler(opencode_options(options))
        if handler is None:
            return None
        config_dir = deployment.root / "opencode_config"
        plugin_path = config_dir / "plugin" / "yoke_tool_hook.js"
        plugin_path.parent.mkdir(parents=True, exist_ok=True)
        plugin_path.write_text(OPENCODE_HOOK_PLUGIN_SOURCE)
        deployment.opencode_config_dir = config_dir
        bridge = OpencodeHookBridge(resolve=self._resolve_hook_request)
        bridge.start()
        return bridge

    def _resolve_hook_request(self, session_id: str, payload: JsonObject) -> Response:
        internal = self._sessions.get(session_id)
        handler = (
            opencode_request_handler(internal.provider_options)
            if internal is not None
            else None
        )
        event, response = resolve_hook_request(payload, handler)
        if internal is not None and internal.current_emit is not None:
            internal.current_emit(
                event.model_copy(
                    update={"kind": EventKind.REQUEST_RESOLVED, "response": response}
                )
            )
        return response

    def _resolve_db_path(self) -> Path:
        if self._db_path_override is not None:
            return self._db_path_override
        # Fixed, HOME-relative path confirmed live in the CodeAlmanac spike
        # this adapter is ported from (2026-07-08) — not affected by
        # OPENCODE_CONFIG_DIR, which only relocates skill/agent discovery.
        return Path.home() / ".local" / "share" / "opencode" / "opencode.db"

    def _send(
        self,
        internal: _OpencodeSession,
        turn: Turn,
        model: str,
        options: RunOptions,
    ) -> Run:
        provider_id, model_id = split_opencode_model(model)
        prompt = turn.prompt
        if internal.instructions and not internal.instructions_sent:
            prompt = f"{internal.instructions}\n\n---\n\n{turn.prompt}"
            internal.instructions_sent = True
        events: list = []
        on_event = options.on_event

        def emit(event) -> None:
            events.append(event)
            if on_event is not None:
                on_event(event)

        # Lets a live tool.execute.before hook call (OpencodeHookBridge,
        # providers/opencode/hooks.py) emit its resolved event into *this*
        # turn's stream — the bridge is a long-lived, process-scoped server
        # (env-var-addressed at process spawn, shared across forks), so it
        # can't bind to one turn's `emit` closure at construction time.
        internal.current_emit = emit
        try:
            return self._send_turn(
                internal, prompt, provider_id, model_id, options, emit, events
            )
        finally:
            internal.current_emit = None

    def _send_turn(
        self,
        internal: _OpencodeSession,
        prompt: str,
        provider_id: str,
        model_id: str,
        options: RunOptions,
        emit: Callable[[Event], None],
        events: list,
    ) -> Run:
        # Emitted first and unconditionally, matching CodexAppServer's
        # _send(): Run.provider_session_id scans events in reverse for the
        # first one carrying provider_session_id, so callers (e.g.
        # CodeAlmanac's transcript-ref linking) depend on this existing at
        # all, not just on Session.provider_session_id being set.
        emit(
            Event(
                kind=EventKind.PROVIDER_SESSION,
                surface=Surface.OPENCODE_SERVER,
                message=f"opencode provider session {internal.session_id}",
                provider_session_id=internal.session_id,
            )
        )

        watchdog = OpencodeProgressWatchdog(
            db_path=internal.db_path,
            root_session_id=internal.session_id,
            on_event=emit,
            poll_interval_seconds=self.poll_interval_seconds,
            stuck_after_seconds=self.stuck_after_seconds,
            known_sessions=internal.known_sessions,
            seen_part_ids=internal.seen_part_ids,
        )
        stop_event = threading.Event()
        watchdog_thread = threading.Thread(
            target=watchdog.run, args=(stop_event,), daemon=True
        )
        watchdog_thread.start()

        effective_options = (
            opencode_options_for_run(options) or internal.provider_options
        )
        permission_watchdog = OpencodePermissionWatchdog(
            base_url=internal.process.base_url,
            session_id=internal.session_id,
            on_event=emit,
            request_handler=opencode_request_handler(effective_options),
            poll_interval_seconds=self.poll_interval_seconds,
            seen_permission_ids=internal.seen_permission_ids,
        )
        permission_thread = threading.Thread(
            target=permission_watchdog.run, args=(stop_event,), daemon=True
        )
        permission_thread.start()

        message_result: dict[str, JsonObject | Exception] = {}

        def _post() -> None:
            try:
                message_result["response"] = http.post_message(
                    internal.process.base_url,
                    internal.session_id,
                    str(internal.cwd),
                    provider_id,
                    model_id,
                    prompt,
                    options.timeout_seconds or OPENCODE_RUN_REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as error:  # noqa: BLE001 - surfaced below
                message_result["error"] = error

        sender_thread = threading.Thread(target=_post, daemon=True)
        sender_thread.start()

        while sender_thread.is_alive():
            if watchdog.stuck_reason is not None:
                # Unwinds and terminates the server below, killing the
                # connection the sender thread is blocked on.
                stop_event.set()
                internal.process.terminate()
                failure = classify_opencode_failure(
                    str(OpencodeStuckToolCallError(watchdog.stuck_reason))
                )
                return Run(
                    provider=self.provider,
                    surface=self.surface,
                    status=RunStatus.FAILED,
                    output=failure.message,
                    events=tuple(events),
                    failure=failure,
                )
            sender_thread.join(timeout=OPENCODE_STUCK_CHECK_INTERVAL_SECONDS)

        stop_event.set()
        watchdog_thread.join(timeout=self.poll_interval_seconds * 2 + 5)
        permission_thread.join(timeout=self.poll_interval_seconds * 2 + 5)

        if "error" in message_result:
            error = message_result["error"]
            failure = classify_opencode_failure(str(error))
            return Run(
                provider=self.provider,
                surface=self.surface,
                status=RunStatus.FAILED,
                output=failure.message,
                events=tuple(events),
                failure=failure,
            )
        response = as_record(message_result["response"])
        info = as_record(response.get("info"))
        raw_parts = response.get("parts")
        parts = (
            [as_record(part) for part in raw_parts]
            if isinstance(raw_parts, list)
            else []
        )
        text = final_text_from_parts(parts)
        usage = parse_opencode_usage(info.get("tokens"))
        return Run(
            provider=self.provider,
            surface=self.surface,
            status=RunStatus.SUCCEEDED,
            output=text or "opencode completed",
            events=tuple(events),
            usage=usage,
        )


def _resolved_permissions(harness: Harness, options: SessionOptions) -> Permissions:
    return options.permissions or harness.permissions or harness.agent.permissions


def _session_permission_block(permissions: Permissions) -> tuple[JsonObject, ...]:
    """Return the session-creation permission block for a resolved posture.

    `Approval.ASK` is the only posture this adapter can honor with a live
    signal now that `GET /permission` + `POST /permission/:id/reply` are
    wired (OpencodePermissionWatchdog, providers/opencode/permissions.py,
    confirmed live in a 2026-07-12 spike) — AUTO and NEVER both mean "don't
    ask", matching Codex's own approval_policy() mapping
    (providers/codex_app/policy.py).
    """

    if permissions.approval is Approval.ASK:
        return http.OPENCODE_ASK_ALL_PERMISSION
    return http.OPENCODE_ALLOW_ALL_PERMISSION


def opencode_options(options: SessionOptions) -> OpencodeOptions | dict[str, object]:
    if options.provider is None:
        return {}
    return options.provider.opencode


def opencode_options_for_run(
    options: RunOptions,
) -> OpencodeOptions | dict[str, object] | None:
    if options.provider is None:
        return None
    return options.provider.opencode


def _model_ids(entries: object) -> tuple[str, ...]:
    if isinstance(entries, dict):
        return tuple(str(key) for key in entries)
    if isinstance(entries, list):
        ids = []
        for entry in entries:
            record = as_record(entry) if isinstance(entry, dict) else {}
            model_id = string_field(record, "id") if record else None
            if model_id is not None:
                ids.append(model_id)
        return tuple(ids)
    return ()


def _session_summary(
    record: JsonObject,
    provider: Provider,
    surface: str,
) -> SessionSummary:
    session_id = string_field(record, "id") or ""
    return SessionSummary(
        provider=provider,
        surface=surface,
        id=session_id,
        provider_session_id=session_id or None,
        title=string_field(record, "title"),
        raw=record,
    )
