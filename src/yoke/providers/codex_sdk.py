"""Codex Python SDK adapter.

This adapter uses the public `openai_codex` package when it is installed. The
raw app-server adapter remains Yoke's deepest Codex integration surface; the
SDK adapter is the supported automation surface for applications that prefer
the published Python wrapper.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Access,
    Approval,
    Authentication,
    AuthMethod,
    Event,
    EventKind,
    Failure,
    Goal,
    GoalRun,
    Harness,
    Login,
    Model,
    Permissions,
    Provider,
    Readiness,
    Run,
    RunStatus,
    Session,
    Turn,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    CodexOptions,
    ForkOptions,
    GoalLoopOptions,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
)
from yoke.providers.codex_app.events import TurnResult, map_notification
from yoke.providers.codex_app.prompts import developer_instructions
from yoke.readiness import run_command
from yoke.structured import OutputSchema, parse_output, provider_schema
from yoke.surfaces import capabilities_for
from yoke.workflows import native_workflow_unsupported

CODEX_INSTALL = "pip install almanac-yoke[codex]"


class CodexPythonSdk:
    """Adapter for the `openai-codex` Python SDK."""

    provider: Provider = "codex"
    surface = "codex_python_sdk"
    capabilities = capabilities_for(provider, surface)

    def __init__(
        self,
        *,
        codex_bin: str | Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.codex_bin = str(codex_bin) if codex_bin is not None else None
        self.config = config or {}
        self._sessions: dict[str, SdkSession] = {}

    async def check(self, harness: Harness) -> Readiness:
        status = await self.auth_status(harness)
        if not status.installed and status.message == "openai_codex is not installed":
            fix = f"Install Codex SDK support with `{CODEX_INSTALL}`."
        elif not status.installed:
            fix = "Install Codex CLI or pass a valid codex_bin."
        elif not status.ready:
            fix = "Authenticate Codex with Harness.login(...) or the Codex CLI."
        else:
            fix = None
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=status.ready,
            message=status.message,
            fix=fix,
        )

    async def auth_status(self, harness: Harness) -> Authentication:
        methods = harness.auth_methods()
        try:
            sdk = openai_codex()
        except ImportError:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=None,
                installed=False,
                authenticated=False,
                compatible=False,
                ready=False,
                message="openai_codex is not installed",
            )
        codex_bin = self.codex_bin or shutil.which("codex")
        if codex_bin is None:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=None,
                installed=False,
                authenticated=False,
                compatible=False,
                ready=False,
                message="codex runtime not found on PATH",
            )
        try:
            runtime = await run_command(codex_bin, "--version", timeout_seconds=3)
        except FileNotFoundError:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=None,
                installed=False,
                authenticated=False,
                compatible=False,
                ready=False,
                message="codex runtime not found",
            )
        except TimeoutError:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=None,
                installed=True,
                authenticated=False,
                compatible=False,
                ready=False,
                message="codex runtime version check timed out",
            )
        if runtime.code != 0:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=None,
                installed=True,
                authenticated=False,
                compatible=False,
                ready=False,
                message=runtime.message or "codex runtime could not start",
            )
        version = getattr(sdk, "__version__", None)
        if harness.credentials.method is not AuthMethod.EXTERNAL:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=harness.credentials.method,
                installed=True,
                authenticated=False,
                compatible=None,
                ready=False,
                message=(
                    "Codex Python SDK credentials are provider-persisted login "
                    "flows; call Harness.login(...) explicitly"
                ),
            )
        client = sdk.AsyncCodex(config=self._codex_config(sdk))
        try:
            async with client as codex:
                await codex.account(refresh_token=False)
        except Exception:
            return Authentication(
                provider=self.provider,
                surface=self.surface,
                methods=methods,
                method=harness.credentials.method,
                installed=True,
                authenticated=False,
                compatible=None,
                ready=False,
                message="Codex runtime is installed but authentication is unavailable",
            )
        return Authentication(
            provider=self.provider,
            surface=self.surface,
            methods=methods,
            method=harness.credentials.method,
            installed=True,
            authenticated=True,
            compatible=None,
            ready=True,
            live_tested=False,
            message=f"openai_codex authenticated{f' ({version})' if version else ''}",
        )

    async def login(
        self,
        harness: Harness,
        method: str,
        *,
        api_key: str | None = None,
    ) -> Login:
        sdk = openai_codex()
        auth_method = AuthMethod(method)
        client = sdk.AsyncCodex(config=self._codex_config(sdk))
        await client.__aenter__()
        try:
            if auth_method is AuthMethod.API_KEY:
                if api_key is None:
                    raise YokeError("api_key is required for API key login.")
                await client.login_api_key(api_key)
                await client.__aexit__(None, None, None)
                return Login(
                    provider=self.provider,
                    surface=self.surface,
                    method=auth_method,
                    message="Codex API key login completed",
                    success=True,
                )
            if auth_method is AuthMethod.CHATGPT:
                handle = await client.login_chatgpt()
                return Login(
                    provider=self.provider,
                    surface=self.surface,
                    method=auth_method,
                    auth_url=str(getattr(handle, "auth_url", "")) or None,
                    message="Open the auth_url to finish ChatGPT login.",
                    raw=AsyncSdkLogin(client=client, handle=handle),
                )
            if auth_method is AuthMethod.DEVICE_CODE:
                handle = await client.login_chatgpt_device_code()
                return Login(
                    provider=self.provider,
                    surface=self.surface,
                    method=auth_method,
                    verification_url=str(getattr(handle, "verification_url", ""))
                    or None,
                    user_code=str(getattr(handle, "user_code", "")) or None,
                    message="Open verification_url and enter user_code.",
                    raw=AsyncSdkLogin(client=client, handle=handle),
                )
        except Exception:
            await client.__aexit__(None, None, None)
            raise
        await client.__aexit__(None, None, None)
        raise UnsupportedFeature(
            f"Codex Python SDK login method is unsupported: {method}"
        )

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        session = await self.start(
            harness,
            SessionOptions(
                goal=options.goal,
                inherit_goal=options.inherit_goal,
                effort=options.effort,
                model=options.model,
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

    async def models(self, harness: Harness) -> tuple[Model, ...]:
        self._require_external_credentials(harness)
        sdk = openai_codex()
        client = sdk.AsyncCodex(config=self._codex_config(sdk))
        async with client as codex:
            return parse_models(await codex.models())

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
                "Codex Python SDK is app-server backed, but Yoke has not found "
                "a documented provider-native workflow DSL for it."
            ),
        )

    async def goal_loop(
        self,
        harness: Harness,
        options: GoalLoopOptions,
    ) -> GoalRun:
        raise UnsupportedFeature(
            "Codex Python SDK runs are caller-bounded today; Yoke has not found "
            "a public SDK method for provider-owned /goal continuation. Use "
            "codex_app_server when you need a Yoke-managed goal-loop handle."
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        self._require_external_credentials(harness)
        sdk = openai_codex()
        permissions = (
            options.permissions or harness.permissions or harness.agent.permissions
        )
        client = sdk.AsyncCodex(config=self._codex_config(sdk))
        await client.__aenter__()
        try:
            thread = await self._thread(client, harness, options, permissions)
        except Exception:
            await client.__aexit__(None, None, None)
            raise
        process = SdkProcess(client=client)
        self._sessions[thread.id] = SdkSession(
            process=process,
            thread=thread,
            model=options.model or harness.agent.model,
        )
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=thread.id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=options.resolve_goal(harness.agent.goal),
            model=options.model or harness.agent.model,
        )

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        return await self._send(session, turn, options=options)

    async def stream(self, session: Session, turn: Turn, options: RunOptions):
        if session.agent is None:
            raise YokeError("Codex SDK session needs an agent.")
        sdk_session = self._session(session)
        permissions = options.permissions or session.permissions
        handle = await sdk_session.thread.turn(
            prompt_with_goal(turn.prompt, options.resolve_goal(session.goal)),
            cwd=str(session.cwd) if session.cwd else None,
            effort=str(options.effort or session.agent.effort)
            if options.effort or session.agent.effort
            else None,
            model=options.model or sdk_session.model,
            sandbox=sandbox(sdk_module=openai_codex(), permissions=permissions),
        )
        sdk_session.active_turn = handle
        try:
            async for event in handle.stream():
                for mapped in sdk_events(event):
                    yield mapped.model_copy(update={"surface": self.surface})
        finally:
            if sdk_session.active_turn is handle:
                sdk_session.active_turn = None

    async def get_goal(self, session: Session) -> Goal | None:
        raise UnsupportedFeature("Codex Python SDK does not expose readable goals.")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Codex Python SDK does not expose mutable goals.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Codex Python SDK does not expose mutable goals.")

    async def interrupt(self, session: Session) -> None:
        sdk_session = self._session(session)
        active_turn = sdk_session.active_turn
        if active_turn is None:
            raise UnsupportedFeature(
                "Codex Python SDK can only interrupt an active streamed turn."
            )
        result = active_turn.interrupt()
        if hasattr(result, "__await__"):
            await result

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        if session.agent is None:
            raise YokeError("Codex SDK session needs an agent.")
        sdk_session = self._session(session)
        sdk = openai_codex()
        permissions = session.permissions or session.agent.permissions
        thread = await sdk_session.process.client.thread_fork(
            session.id,
            approval_mode=approval_mode(sdk, permissions),
            cwd=str(session.cwd) if session.cwd else None,
            developer_instructions=developer_instructions(session.agent),
            ephemeral=options.ephemeral,
            model=sdk_session.model,
            sandbox=sandbox(sdk, permissions),
        )
        sdk_session.process.retain()
        self._sessions[thread.id] = SdkSession(
            process=sdk_session.process,
            thread=thread,
            model=sdk_session.model,
        )
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=thread.id,
            agent=session.agent,
            cwd=session.cwd,
            permissions=permissions,
            goal=session.goal,
            model=session.model,
        )

    async def close(self, session: Session) -> None:
        sdk_session = self._sessions.pop(session.id, None)
        if sdk_session is not None:
            await sdk_session.process.release()

    async def _thread(
        self,
        client: Any,
        harness: Harness,
        options: SessionOptions,
        permissions: Permissions,
    ) -> Any:
        sdk = openai_codex()
        kwargs = {
            "approval_mode": approval_mode(sdk, permissions),
            "config": codex_config(options),
            "cwd": str(harness.cwd),
            "developer_instructions": developer_instructions(harness.agent),
            "model": options.model or harness.agent.model,
            "sandbox": sandbox(sdk, permissions),
        }
        if options.resume:
            return await client.thread_resume(options.resume, **kwargs)
        return await client.thread_start(
            ephemeral=False,
            **kwargs,
        )

    async def _send(
        self,
        session: Session,
        turn: Turn,
        *,
        output_schema: OutputSchema | None = None,
        options: RunOptions | None = None,
    ) -> Run:
        if session.agent is None:
            raise YokeError("Codex SDK session needs an agent.")
        sdk_session = self._session(session)
        run_options = options or RunOptions(output_schema=output_schema)
        schema = run_options.output_schema or output_schema
        permissions = run_options.permissions or session.permissions
        try:
            result = await sdk_session.thread.run(
                prompt_with_goal(turn.prompt, run_options.resolve_goal(session.goal)),
                cwd=str(session.cwd) if session.cwd else None,
                effort=str(run_options.effort or session.agent.effort)
                if run_options.effort or session.agent.effort
                else None,
                model=run_options.model or sdk_session.model,
                output_schema=provider_schema(schema),
                sandbox=sandbox(openai_codex(), permissions),
            )
        except Exception as exc:
            return Run(
                provider=self.provider,
                surface=self.surface,
                status=RunStatus.FAILED,
                output=str(exc),
                failure=Failure(message=str(exc), raw=repr(exc)),
                session=session,
                requested_model=run_options.model or sdk_session.model,
            )
        output = final_response(result)
        structured = parse_output(output or "", schema)
        failure = turn_failure(result) or structured.failure
        return Run(
            provider=self.provider,
            surface=self.surface,
            status=RunStatus.FAILED if failure else RunStatus.SUCCEEDED,
            output=output,
            data=structured.data,
            events=tuple(
                event.model_copy(update={"surface": self.surface})
                for event in result_events(result)
            ),
            session=session,
            usage=usage_dict(getattr(result, "usage", None)),
            failure=failure,
            requested_model=run_options.model or sdk_session.model,
        )

    def _session(self, session: Session) -> SdkSession:
        try:
            return self._sessions[session.id]
        except KeyError as exc:
            raise YokeError(f"Codex SDK session is not live: {session.id}") from exc

    def _codex_config(self, sdk: ModuleType) -> Any | None:
        config = getattr(sdk, "CodexConfig", None)
        if config is None:
            return None
        codex_bin = self.codex_bin or shutil.which("codex")
        if codex_bin is None:
            return None
        return config(codex_bin=codex_bin)

    def _require_external_credentials(self, harness: Harness) -> None:
        method = harness.credentials.method
        if method is AuthMethod.EXTERNAL:
            return
        raise UnsupportedFeature(
            "Codex Python SDK runtime credentials are unsupported because its "
            "login methods persist provider state; call Harness.login(...) explicitly"
        )


@dataclass(slots=True)
class SdkProcess:
    """Reference-counted live Codex SDK client."""

    client: Any
    refs: int = 1
    closed: bool = False

    def retain(self) -> None:
        if self.closed:
            raise YokeError("Codex SDK client is already closed.")
        self.refs += 1

    async def release(self) -> None:
        if self.closed:
            return
        self.refs -= 1
        if self.refs <= 0:
            self.closed = True
            await self.client.__aexit__(None, None, None)


@dataclass(slots=True)
class SdkSession:
    """Live Codex SDK client and thread pair."""

    process: SdkProcess
    thread: Any
    model: str | None = None
    active_turn: Any | None = None


@dataclass(slots=True)
class AsyncSdkLogin:
    """Keeps a Codex SDK client alive until the login handle completes."""

    client: Any
    handle: Any

    async def wait(self) -> Any:
        try:
            result = self.handle.wait()
            if hasattr(result, "__await__"):
                result = await result
            return result
        finally:
            await self.client.__aexit__(None, None, None)


def openai_codex() -> ModuleType:
    try:
        import openai_codex as sdk
    except ImportError as exc:
        raise ImportError("openai_codex is not installed") from exc
    return sdk


def codex_config(options: SessionOptions) -> dict[str, Any] | None:
    provider = options.provider
    if provider is None:
        return None
    codex = provider.codex
    if isinstance(codex, CodexOptions):
        return codex.raw or None
    return codex.get("raw") if isinstance(codex.get("raw"), dict) else codex


def approval_mode(sdk: ModuleType, permissions: Permissions) -> Any:
    modes = sdk.ApprovalMode
    if permissions.approval is Approval.NEVER:
        return modes.deny_all
    return modes.auto_review


def sandbox(sdk_module: ModuleType, permissions: Permissions | None) -> Any:
    modes = sdk_module.Sandbox
    access = (permissions or Permissions()).access
    if access is Access.FULL:
        return modes.full_access
    if access is Access.WRITE:
        return modes.workspace_write
    return modes.read_only


def prompt_with_goal(prompt: str, goal: Goal | None) -> str:
    if goal is None:
        return prompt
    return (
        f"Goal: {goal.objective}\n\n"
        "Work toward this goal and stop when it is complete, blocked, or unsafe "
        "to continue.\n\n"
        f"User request:\n{prompt}"
    )


def final_response(result: Any) -> str | None:
    response = getattr(result, "final_response", None)
    return str(response) if response is not None else None


def turn_failure(result: Any) -> Failure | None:
    status = getattr(getattr(result, "status", None), "value", None)
    if status is None:
        status = str(getattr(result, "status", ""))
    if "fail" not in str(status).lower():
        return None
    error = getattr(result, "error", None)
    message = getattr(error, "message", None) or "Codex SDK turn failed"
    return Failure(message=str(message), raw=repr(error))


def result_events(result: Any) -> list[Event]:
    events: list[Event] = []
    output = final_response(result)
    if output:
        events.append(Event(kind="text", message=output, raw=result))
    events.append(
        Event(
            kind="done",
            message=str(getattr(getattr(result, "status", None), "value", "done")),
            raw=result,
        )
    )
    return events


def sdk_events(event: Any) -> list[Event]:
    """Map Codex Python SDK notifications through the app-server mapper."""

    notification = sdk_notification(event)
    method = notification.get("method")
    if isinstance(method, str):
        events = map_notification(notification, TurnResult())
        if events:
            return [mapped.model_copy(update={"raw": event}) for mapped in events]
    return [sdk_stream_event(event, method)]


def sdk_event(event: Any) -> Event:
    """Return the first Yoke event for a Codex Python SDK notification."""

    return sdk_events(event)[0]


def sdk_stream_event(event: Any, method: object | None = None) -> Event:
    if method is None:
        method = getattr(event, "method", None)
    return Event(
        kind=EventKind.STREAM_EVENT,
        message=str(method) if method is not None else None,
        raw=event,
    )


def sdk_notification(event: Any) -> dict[str, Any]:
    """Convert a typed SDK notification into the app-server JSON shape."""

    if isinstance(event, dict):
        return event
    if hasattr(event, "model_dump"):
        data = event.model_dump(by_alias=True, exclude_none=True)
        return data if isinstance(data, dict) else {}
    method = getattr(event, "method", None)
    params = getattr(event, "params", None)
    data: dict[str, Any] = {}
    if method is not None:
        data["method"] = str(method)
    if params is not None:
        data["params"] = sdk_value(params)
    return data


def sdk_value(value: Any) -> Any:
    """Return a JSON-like value from SDK pydantic objects and simple fakes."""

    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, dict):
        return {key: sdk_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sdk_value(item) for item in value]
    if isinstance(value, tuple):
        return [sdk_value(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: sdk_value(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def usage_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        data = value.model_dump()
        return data if isinstance(data, dict) else None
    fields = {
        name: getattr(value, name)
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "total_processed_tokens",
            "max_tokens",
        )
        if hasattr(value, name)
    }
    return fields or None


def parse_models(response: Any) -> tuple[Model, ...]:
    values = getattr(response, "models", None)
    if values is None:
        values = getattr(response, "data", None)
    if values is None and isinstance(response, dict):
        values = response.get("models", response.get("data"))
    if not isinstance(values, list):
        return ()
    return tuple(model for item in values if (model := parse_model(item)) is not None)


def parse_model(value: Any) -> Model | None:
    model_id = field(value, "id") or field(value, "name")
    if model_id is None:
        return None
    return Model(
        id=str(model_id),
        hidden=field(value, "hidden") is True,
        reasoning_efforts=reasoning_efforts(
            first_field(
                value,
                "supported_reasoning_efforts",
                "supportedReasoningEfforts",
            )
        ),
        raw=value,
    )


def reasoning_efforts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    efforts: list[str] = []
    for item in value:
        effort = (
            item
            if isinstance(item, str)
            else first_field(item, "reasoning_effort", "reasoningEffort")
        )
        if effort is not None:
            efforts.append(str(effort))
    return tuple(efforts)


def field(value: Any, name: str) -> Any | None:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def first_field(value: Any, *names: str) -> Any | None:
    """Return the first present SDK attribute or wire-format mapping field."""

    for name in names:
        candidate = field(value, name)
        if candidate is not None:
            return candidate
    return None
