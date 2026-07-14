"""Public Yoke language.

The models in this module are intentionally provider-neutral. Claude and Codex
mechanics belong behind provider ports, not in these objects.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)

T = TypeVar("T")


class YokeModel(BaseModel):
    """Base model for public Yoke values."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def run_blocking(factory: Any) -> T:
    """Run an async Yoke operation from synchronous code."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    raise RuntimeError("Yoke sync methods cannot run inside an active event loop.")


async def collect_events(events: AsyncIterator[Event]) -> tuple[Event, ...]:
    """Collect an async event stream for sync callers."""

    return tuple([event async for event in events])


class Effort(StrEnum):
    """Provider-neutral effort hint."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Provider(StrEnum):
    """Provider family."""

    CLAUDE = "claude"
    CODEX = "codex"


class Surface(StrEnum):
    """Concrete provider entrypoint."""

    CLAUDE_PYTHON_SDK = "claude_python_sdk"
    CLAUDE_TYPESCRIPT_SDK = "claude_typescript_sdk"
    CLAUDE_CLI = "claude_cli"
    CODEX_CLI = "codex_cli"
    CODEX_PYTHON_SDK = "codex_python_sdk"
    CODEX_TYPESCRIPT_SDK = "codex_typescript_sdk"
    CODEX_APP_SERVER = "codex_app_server"


class Channel(StrEnum):
    """Broad way a provider exposes a surface."""

    CLI = "cli"
    SDK = "sdk"
    APP_SERVER = "app_server"
    CUSTOM = "custom"


def normalize_surface(value: object) -> object:
    """Normalize known surface strings while preserving custom surfaces."""

    if value == "auto":
        return None
    if isinstance(value, str):
        try:
            return Surface(value)
        except ValueError:
            return value
    return value


def normalize_provider_surface(provider: object, surface: object) -> object:
    """Normalize friendly surface aliases for a known provider."""

    if surface in (None, "auto"):
        return None
    if not isinstance(surface, str):
        return surface
    surface_text = surface.strip()
    surface_key = surface_text.replace("-", "_")
    try:
        provider_value = Provider(provider)
    except (TypeError, ValueError):
        return surface_text
    try:
        return Surface(surface_key)
    except ValueError:
        pass
    aliases: dict[Provider, dict[str, Surface]] = {
        Provider.CLAUDE: {
            "sdk": Surface.CLAUDE_PYTHON_SDK,
            "python": Surface.CLAUDE_PYTHON_SDK,
            "python_sdk": Surface.CLAUDE_PYTHON_SDK,
            "agent_sdk": Surface.CLAUDE_PYTHON_SDK,
            "cli": Surface.CLAUDE_CLI,
            "ts": Surface.CLAUDE_TYPESCRIPT_SDK,
            "typescript": Surface.CLAUDE_TYPESCRIPT_SDK,
            "typescript_sdk": Surface.CLAUDE_TYPESCRIPT_SDK,
        },
        Provider.CODEX: {
            "cli": Surface.CODEX_CLI,
            "sdk": Surface.CODEX_PYTHON_SDK,
            "python": Surface.CODEX_PYTHON_SDK,
            "python_sdk": Surface.CODEX_PYTHON_SDK,
            "app": Surface.CODEX_APP_SERVER,
            "app_server": Surface.CODEX_APP_SERVER,
            "appserver": Surface.CODEX_APP_SERVER,
            "ts": Surface.CODEX_TYPESCRIPT_SDK,
            "typescript": Surface.CODEX_TYPESCRIPT_SDK,
            "typescript_sdk": Surface.CODEX_TYPESCRIPT_SDK,
        },
    }
    return aliases[provider_value].get(surface_key, surface_text)


def split_provider_surface(
    provider: object,
    surface: object = None,
) -> tuple[object, object]:
    """Split compact provider specs like ``codex:app``.

    The compact form is input sugar only. Public models still store the
    provider and the resolved surface separately.
    """

    if not isinstance(provider, str) or ":" not in provider:
        return provider, surface
    provider_part, embedded_surface = provider.split(":", 1)
    provider_part = provider_part.strip()
    embedded_surface = embedded_surface.strip()
    if not provider_part or not embedded_surface:
        return provider, surface
    if surface not in (None, "auto"):
        embedded = normalize_provider_surface(provider_part, embedded_surface)
        explicit = normalize_provider_surface(provider_part, surface)
        if embedded != explicit:
            raise ValueError(
                "provider surface spec conflicts with explicit surface: "
                f"{provider!r} vs {surface!r}"
            )
        return provider_part, explicit
    return provider_part, embedded_surface


class Access(StrEnum):
    """Filesystem access requested for provider tools."""

    READ = "read"
    WRITE = "write"
    FULL = "full"


class Approval(StrEnum):
    """Approval posture requested from the provider."""

    NEVER = "never"
    ASK = "ask"
    AUTO = "auto"


class AuthMethod(StrEnum):
    """Provider authentication method."""

    CHATGPT = "chatgpt"
    DEVICE_CODE = "device_code"
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    EXTERNAL = "external"


class Credentials(YokeModel):
    """Runtime-only credentials supplied directly to a harness.

    Credentials are deliberately excluded from Harness serialization and repr.
    ``external`` means to reuse the provider's existing local login or normal
    environment discovery.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    method: AuthMethod = AuthMethod.EXTERNAL
    secret: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_secret(self) -> Credentials:
        needs_secret = self.method in (AuthMethod.API_KEY, AuthMethod.OAUTH_TOKEN)
        if needs_secret and self.secret is None:
            raise ValueError(f"{self.method.value} credentials require a secret")
        if not needs_secret and self.secret is not None:
            raise ValueError(f"{self.method.value} credentials do not accept a secret")
        return self

    @field_validator("secret")
    @classmethod
    def require_nonempty_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value().strip()
        if not secret:
            raise ValueError("credential secret must not be empty")
        return SecretStr(secret)

    @classmethod
    def auto(cls) -> Credentials:
        return cls()

    @classmethod
    def api_key(cls, value: str) -> Credentials:
        return cls(method=AuthMethod.API_KEY, secret=value)

    @classmethod
    def oauth_token(cls, value: str) -> Credentials:
        return cls(method=AuthMethod.OAUTH_TOKEN, secret=value)

    def reveal(self) -> str | None:
        """Return the secret only at the provider boundary."""

        return self.secret.get_secret_value() if self.secret is not None else None


class Authentication(YokeModel):
    """Non-secret authentication and runtime readiness metadata."""

    provider: Provider
    surface: Surface | str
    methods: tuple[AuthMethod, ...]
    method: AuthMethod | None = None
    installed: bool
    authenticated: bool | None
    compatible: bool | None
    ready: bool
    live_tested: bool = False
    message: str


class GoalStatus(StrEnum):
    """Provider-neutral goal status."""

    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    USAGE_LIMITED = "usage_limited"
    BUDGET_LIMITED = "budget_limited"
    COMPLETE = "complete"


class RunStatus(StrEnum):
    """Provider-neutral run status."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Failure(YokeModel):
    """Provider-neutral failure details."""

    message: str
    code: str | None = None
    fix: str | None = None
    raw: str | None = None

    @field_validator("message")
    @classmethod
    def require_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("failure message is required")
        return value


class ToolKind(StrEnum):
    """Provider-neutral tool display kind."""

    READ = "read"
    WRITE = "write"
    EDIT = "edit"
    SEARCH = "search"
    SHELL = "shell"
    MCP = "mcp"
    WEB = "web"
    AGENT = "agent"
    IMAGE = "image"
    UNKNOWN = "unknown"


class ToolStatus(StrEnum):
    """Provider-neutral tool lifecycle status."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"


class EventKind(StrEnum):
    """Provider-neutral event kind."""

    TEXT_DELTA = "text_delta"
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    TOOL_SUMMARY = "tool_summary"
    TOOL_REQUEST = "tool_request"
    APPROVAL_REQUEST = "approval_request"
    USER_INPUT_REQUEST = "user_input_request"
    REQUEST_RESOLVED = "request_resolved"
    CONTEXT_USAGE = "context_usage"
    PROVIDER_SESSION = "provider_session"
    WARNING = "warning"
    ERROR = "error"
    DONE = "done"
    HOOK = "hook"
    RATE_LIMIT = "rate_limit"
    GOAL_UPDATED = "goal_updated"
    GOAL_CLEARED = "goal_cleared"
    STREAM_EVENT = "stream_event"
    UNKNOWN = "unknown"


class RequestKind(StrEnum):
    """Provider-neutral provider request kind."""

    APPROVAL = "approval"
    USER_INPUT = "user_input"
    TOOL = "tool"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class Model(YokeModel):
    """Provider model available to a harness surface."""

    id: str
    hidden: bool = False
    reasoning_efforts: tuple[str, ...] = ()
    raw: object | None = None


class ModelSource(StrEnum):
    """Where the requested model for a run or session came from."""

    RUN = "run"
    SESSION = "session"
    AGENT = "agent"
    PROVIDER_DEFAULT = "provider_default"


class ModelSelection(YokeModel):
    """How Yoke will pass model selection to a provider surface."""

    model: str | None = None
    source: ModelSource = ModelSource.PROVIDER_DEFAULT
    provider: Provider
    surface: Surface | str
    channel: Channel
    model_listing: str
    verifiable: bool = False
    note: str


class Readiness(YokeModel):
    """Provider surface readiness."""

    provider: Provider
    surface: Surface | str | None = None
    available: bool
    message: str
    fix: str | None = None
    raw: str | None = None

    @field_validator("message")
    @classmethod
    def require_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("readiness message is required")
        return value

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

class Login(YokeModel):
    """Provider login flow result."""

    provider: Provider
    surface: Surface | str | None = None
    method: AuthMethod | str
    message: str | None = None
    auth_url: str | None = None
    verification_url: str | None = None
    user_code: str | None = None
    success: bool | None = None
    raw: object | None = Field(default=None, exclude=True, repr=False)

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    @field_validator("method", mode="before")
    @classmethod
    def normalize_known_method(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return AuthMethod(value)
            except ValueError:
                return value
        return value

    async def wait(self) -> Login:
        """Wait for an interactive login handle when the provider returns one."""

        if self.raw is None:
            return self
        wait = getattr(self.raw, "wait", None)
        if wait is None:
            return self
        result = wait()
        if inspect.isawaitable(result):
            result = await result
        success = getattr(result, "success", self.success)
        message = getattr(result, "message", self.message)
        return self.model_copy(
            update={
                "success": success,
                "message": str(message) if message is not None else self.message,
                "raw": result,
            }
        )

    def wait_sync(self) -> Login:
        """Wait for an interactive login handle from synchronous code."""

        return run_blocking(lambda: self.wait())


class SessionSummary(YokeModel):
    """Stored provider session/thread summary."""

    provider: Provider
    surface: Surface | str | None = None
    id: str
    provider_session_id: str | None = None
    title: str | None = None
    tag: str | None = None
    summary: str | None = None
    cwd: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    raw: object | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)


class SessionMessage(YokeModel):
    """Stored provider session/thread message."""

    provider: Provider
    surface: Surface | str | None = None
    session_id: str
    id: str | None = None
    role: str | None = None
    content: object | None = None
    raw: object | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)


class SessionList(YokeModel):
    """Page of stored provider sessions/threads."""

    provider: Provider
    surface: Surface | str | None = None
    sessions: tuple[SessionSummary, ...] = ()
    next_cursor: str | None = None
    raw: object | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)


class SessionHistory(YokeModel):
    """Stored provider session/thread with optional messages."""

    provider: Provider
    surface: Surface | str | None = None
    session: SessionSummary
    messages: tuple[SessionMessage, ...] = ()
    raw: object | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)


class Goal(YokeModel):
    """Session-attached objective state."""

    objective: str
    status: GoalStatus = GoalStatus.ACTIVE
    token_budget: int | None = None
    tokens_used: int | None = None
    time_used_seconds: int | None = None

    def __init__(self, objective: str | None = None, **data: Any):
        if objective is not None:
            data["objective"] = objective
        super().__init__(**data)

    @field_validator("objective")
    @classmethod
    def require_objective(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("goal objective is required")
        return value


class GoalRun(YokeModel):
    """Handle returned when a provider-owned goal loop starts."""

    provider: Provider
    surface: Surface | str | None = None
    goal: Goal
    session: Session
    auto_continues: bool = True
    status: RunStatus = RunStatus.SUCCEEDED
    failure: Failure | None = None
    raw: object | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    @property
    def ok(self) -> bool:
        """Whether the provider accepted the goal loop request."""

        return self.status == RunStatus.SUCCEEDED

    def raise_for_status(self) -> GoalRun:
        """Raise if the goal loop failed, otherwise return this result."""

        if self.ok:
            return self
        raise_status_error("goal_loop", self.failure)


class Skill(YokeModel):
    """Reusable capability loaded from text or a folder."""

    name: str | None = None
    description: str | None = None
    path: Path | None = None
    instructions: str | None = None

    @classmethod
    def from_path(cls, path: str | Path, name: str | None = None) -> Skill:
        return cls(path=Path(path), name=name)

    @classmethod
    def from_text(
        cls,
        instructions: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Skill:
        return cls(name=name, description=description, instructions=instructions)

    @model_validator(mode="after")
    def require_source(self) -> Skill:
        if self.path is None and self.instructions is None:
            raise ValueError("skill needs path or instructions")
        return self


class Tools(YokeModel):
    """High-level tool affordances an agent may use."""

    read: bool = True
    write: bool = False
    shell: bool = False
    web: bool = False
    agent: bool = False


class Permissions(YokeModel):
    """Execution permissions requested from a provider."""

    access: Access = Access.READ
    approval: Approval = Approval.ASK
    network: bool = False


class Agent(YokeModel):
    """Agent definition that can compile to Claude or Codex."""

    root: Path | None = None
    instructions: str | None = None
    description: str | None = None
    model: str | None = None
    effort: Effort | str | None = None
    goal: Goal | None = None
    tools: Tools = Field(default_factory=Tools)
    permissions: Permissions = Field(default_factory=Permissions)
    skills: tuple[Skill, ...] = ()
    subagents: dict[str, Agent] = Field(default_factory=dict)
    workflows: dict[str, Workflow] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_folder(cls, path: str | Path) -> Agent:
        """Load an agent from a Yoke folder."""

        from yoke.loader import load

        return load(path)

    def bundle(
        self,
        *,
        provider: Provider | str,
        surface: Surface | str | None = None,
    ):
        """Compile this agent into provider-native filesystem artifacts."""

        from yoke.artifacts import bundle

        return bundle(self, provider=provider, surface=surface)

    def save(
        self,
        path: str | Path,
        *,
        overwrite: bool = False,
        allow_runtime_only: bool = False,
    ) -> tuple[Path, ...]:
        """Write this agent as a Yoke-native folder."""

        from yoke.folders import save

        return save(
            self,
            path,
            overwrite=overwrite,
            allow_runtime_only=allow_runtime_only,
        )

    def features(self) -> tuple[Any, ...]:
        """Return provider features implied by this agent definition."""

        from yoke.capabilities import Feature

        features: list[Feature] = []

        def add(feature: Feature) -> None:
            if feature not in features:
                features.append(feature)

        if self.goal is not None:
            add(Feature.GOAL)
        if self.skills:
            add(Feature.SKILLS)
        if self.subagents:
            add(Feature.DECLARED_SUBAGENTS)
        if self.workflows:
            add(Feature.WORKFLOW)
        for subagent in self.subagents.values():
            for feature in subagent.features():
                add(feature)
        return tuple(features)

    @model_validator(mode="after")
    def require_useful_body(self) -> Agent:
        if self.instructions is None and self.description is None:
            raise ValueError("agent needs instructions or description")
        return self


class Collection(YokeModel):
    """A folder of named Yoke agents."""

    root: Path
    agents: dict[str, Path]
    default_provider: str | None = None

    @classmethod
    def from_folder(cls, path: str | Path) -> Collection:
        """Load an agent collection from ``agents/yoke.yaml``."""

        from yoke.loader import load_collection

        return load_collection(path)

    def agent(self, name: str) -> Agent:
        """Load one named agent from this collection."""

        try:
            path = self.agents[name]
        except KeyError as exc:
            choices = ", ".join(sorted(self.agents)) or "none"
            raise KeyError(
                f"unknown agent {name!r}; available agents: {choices}"
            ) from exc
        return Agent.from_folder(self.root / path)

    def names(self) -> tuple[str, ...]:
        """Return agent names in stable order."""

        return tuple(sorted(self.agents))


class Step(YokeModel):
    """One workflow step."""

    name: str
    agent: str = "main"
    prompt: str
    depends_on: tuple[str, ...] = ()
    output_schema: Any | None = None
    run: Any | None = None


class WorkflowLanguage(StrEnum):
    """Workflow script language."""

    JAVASCRIPT = "javascript"
    PYTHON = "python"


class WorkflowRunMode(StrEnum):
    """How a workflow execution was performed."""

    YOKE_PORTABLE = "yoke_portable"
    PROVIDER_NATIVE = "provider_native"


class Workflow(YokeModel):
    """Named orchestration recipe over agent calls."""

    name: str
    description: str | None = None
    handler: Callable[..., Any] | None = None
    program_path: Path | None = None
    script: str | None = None
    script_path: Path | None = None
    native_name: str | None = None
    args: Any | None = None
    resume_from_run_id: str | None = None
    language: WorkflowLanguage = WorkflowLanguage.JAVASCRIPT
    steps: tuple[Step, ...] = ()

    def __init__(self, name: str | None = None, **data: Any):
        if name is not None:
            data["name"] = name
        super().__init__(**data)

    def run(self, handler: Callable[..., Any]) -> Workflow:
        """Return a copy of this workflow with its Python program attached."""

        return self.model_copy(update={"handler": handler})

    @classmethod
    def from_program(
        cls,
        name: str,
        path: str | Path,
        *,
        description: str | None = None,
        args: Any | None = None,
    ) -> Workflow:
        """Build a Python-authored workflow program from a file path."""

        return cls(
            name=name,
            description=description,
            program_path=Path(path),
            args=args,
            language=WorkflowLanguage.PYTHON,
        )

    @classmethod
    def from_script(
        cls,
        name: str,
        script: str,
        *,
        description: str | None = None,
        args: Any | None = None,
    ) -> Workflow:
        """Build a provider-native script workflow."""

        return cls(name=name, description=description, script=script, args=args)

    @classmethod
    def from_file(
        cls,
        name: str,
        path: str | Path,
        *,
        description: str | None = None,
        args: Any | None = None,
    ) -> Workflow:
        """Build a provider-native workflow from a script path."""

        return cls(
            name=name,
            description=description,
            script_path=Path(path),
            args=args,
        )

    @classmethod
    def from_name(
        cls,
        name: str,
        *,
        description: str | None = None,
        args: Any | None = None,
        resume_from_run_id: str | None = None,
    ) -> Workflow:
        """Build a provider-native named workflow invocation."""

        return cls(
            name=name,
            description=description,
            native_name=name,
            args=args,
            resume_from_run_id=resume_from_run_id,
        )

    @property
    def native(self) -> bool:
        """Whether this workflow requires a provider-native workflow primitive."""

        return any(
            (
                self.script is not None and bool(self.script.strip()),
                self.script_path is not None,
                self.native_name is not None,
                self.resume_from_run_id is not None,
            )
        )

    def native_input(self) -> dict[str, Any]:
        """Return Claude-style Workflow tool input fields."""

        data: dict[str, Any] = {}
        if self.script is not None and self.script.strip():
            data["script"] = self.script
        if self.native_name is not None:
            data["name"] = self.native_name
        if self.script_path is not None:
            data["scriptPath"] = str(self.script_path)
        if self.args is not None:
            data["args"] = self.args
        if self.resume_from_run_id is not None:
            data["resumeFromRunId"] = self.resume_from_run_id
        return data

    @model_validator(mode="after")
    def require_one_body(self) -> Workflow:
        has_steps = bool(self.steps)
        has_native = self.native
        has_program = self.handler is not None or self.program_path is not None
        body_count = sum((has_steps, has_native, has_program))
        if body_count > 1:
            raise ValueError(
                "workflow can have only one body: Python handler, portable "
                "steps, or native workflow body; use either portable steps or "
                "a native workflow body"
            )
        native_input = self.native_input()
        if has_native and not any(
            key in native_input for key in ("script", "name", "scriptPath")
        ):
            raise ValueError(
                "native workflow needs script, native_name, or script_path"
            )
        return self


class StepResult(YokeModel):
    """Result for one workflow step."""

    step: str
    agent: str = "main"
    mode: WorkflowRunMode = WorkflowRunMode.YOKE_PORTABLE
    provider: Provider | str | None = None
    surface: Surface | str | None = None
    depends_on: tuple[str, ...] = ()
    prompt: str | None = None
    run: Run


class WorkflowRun(YokeModel):
    """Result for a workflow execution."""

    workflow: str
    mode: WorkflowRunMode = WorkflowRunMode.YOKE_PORTABLE
    run_id: str | None = None
    resume_from_run_id: str | None = None
    provider: Provider | str | None = None
    surface: Surface | str | None = None
    status: RunStatus = RunStatus.SUCCEEDED
    steps: tuple[StepResult, ...] = ()
    traces: tuple[WorkflowTrace, ...] = ()
    output: str | None = None
    data: Any | None = None
    failure: Failure | None = None
    failed_step_name: str | None = None
    interrupted_steps: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether the workflow succeeded."""

        return self.status == RunStatus.SUCCEEDED

    @property
    def failed_step(self) -> StepResult | None:
        """Return the first failed step result, if any."""

        for step in self.steps:
            if not step.run.ok:
                return step
        return None

    def raise_for_status(self) -> WorkflowRun:
        """Raise if the workflow failed, otherwise return this result."""

        if self.ok:
            return self
        raise_status_error("workflow", self.failure, self.output)


class WorkflowTrace(YokeModel):
    """Trace item emitted while a Yoke workflow program runs."""

    kind: str
    id: str | None = None
    cached: bool = False
    name: str | None = None
    phase: str | None = None
    agent: str | None = None
    prompt: str | None = None
    output: str | None = None
    data: Any | None = None
    run: Run | None = None


class Harness(YokeModel):
    """Binds an agent to a provider and working directory.

    The public object has methods because the common case should read well:
    `await Harness(...).run("...")`. Provider mechanics still live behind the
    adapter port.
    """

    provider: Provider
    surface: Surface | str | None = None
    channel: Channel | None = None
    agent: Agent
    cwd: Path
    permissions: Permissions | None = None
    environment: dict[str, str] = Field(
        default_factory=dict,
        exclude=True,
        repr=False,
    )
    runtime_root: Path | None = Field(default=None, exclude=True, repr=False)
    credentials: Credentials = Field(
        default_factory=Credentials.auto,
        exclude=True,
        repr=False,
    )

    def __init__(self, provider: Provider | str | None = None, **data: Any):
        if provider is not None:
            data["provider"] = provider
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def normalize_surface_alias(cls, data: object) -> object:
        if isinstance(data, dict):
            provider, surface = split_provider_surface(
                data.get("provider"),
                data.get("surface"),
            )
            return {
                **data,
                "provider": provider,
                "surface": normalize_provider_surface(provider, surface),
            }
        return data

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    @model_validator(mode="after")
    def keep_runtime_outside_working_directory(self) -> Harness:
        """Reserve in-project files for explicit bundle export only."""

        if self.runtime_root is None:
            return self
        cwd = self.cwd.expanduser().resolve()
        runtime_root = self.runtime_root.expanduser().resolve()
        if runtime_root == cwd or runtime_root.is_relative_to(cwd):
            raise ValueError(
                "runtime_root must be outside cwd; use agent.bundle(...).write(...) "
                "for explicit project files"
            )
        return self

    def with_adapter(self, adapter: Any) -> Harness:
        """Register an adapter and return this harness.

        This keeps examples readable while still letting embedded apps own
        adapter construction explicitly.
        """

        from yoke.adapters import register

        register(adapter)
        return self

    def require(
        self,
        *features: Any,
        channel: Channel | str | None = None,
        runnable: bool = True,
    ) -> Harness:
        """Return a harness whose surface satisfies the requested features.

        If this harness has no explicit surface, Yoke selects the best known
        surface for the provider. If a surface is already set, Yoke validates
        that exact surface instead of silently switching it. By default,
        selection only considers surfaces this Yoke package can run.
        """

        effective_channel = channel if channel is not None else self.channel
        if not features and effective_channel is None:
            return self
        plan = surface_plan(
            provider=self.provider,
            surface=self.surface,
            features=features,
            channel=effective_channel,
            runnable=runnable,
        ).raise_for_status()
        if self.surface is None:
            return self.model_copy(update={"surface": plan.profile.surface})
        return self

    def plan(
        self,
        options: Any | None = None,
        *,
        features: tuple[Any, ...] = (),
        channel: Channel | str | None = None,
        runnable: bool = True,
    ):
        """Return the surface plan Yoke would use for these requirements."""

        effective_channel = first_present(
            channel,
            option_channel(options),
            self.channel,
        )
        required = self._features_for_agent_and_options(options)
        required = (*required, *features)
        return surface_plan(
            provider=self.provider,
            surface=self.surface,
            features=required,
            channel=effective_channel,
            runnable=runnable,
        )

    def explain(
        self,
        options: Any | None = None,
        *,
        features: tuple[Any, ...] = (),
        channel: Channel | str | None = None,
        runnable: bool = True,
    ):
        """Explain how this agent/options shape maps to a provider surface."""

        from yoke.capabilities import Explanation

        plan = self.plan(
            options,
            features=features,
            channel=channel,
            runnable=runnable,
        )
        return Explanation.from_plan(
            plan,
            model=self.model_selection(options),
        )

    async def run(self, prompt: str, options: Any | None = None) -> Run:
        """Execute one convenience run."""

        from yoke.adapters import adapter_for
        from yoke.options import RunOptions

        run_options = (
            options
            if isinstance(options, RunOptions)
            else RunOptions.model_validate(options or {})
        )
        harness = self._require_run_options(run_options)
        return await adapter_for(harness.provider, harness.surface).run(
            harness,
            prompt,
            run_options,
        )

    def run_sync(self, prompt: str, options: Any | None = None) -> Run:
        """Execute one convenience run from synchronous code."""

        return run_blocking(lambda: self.run(prompt, options))

    async def stream(
        self,
        prompt: str,
        options: Any | None = None,
    ) -> AsyncIterator[Event]:
        """Execute one streamed turn in a short-lived provider session."""

        from yoke.capabilities import Feature
        from yoke.options import RunOptions, SessionOptions

        run_options = (
            options
            if isinstance(options, RunOptions)
            else RunOptions.model_validate(options or {})
        )
        harness = self.require(
            Feature.STREAMING,
            *self._features_for_agent_and_options(run_options),
            channel=option_channel(run_options),
        )
        session = await harness.start(
            SessionOptions(
                channel=run_options.channel,
                goal=run_options.goal,
                inherit_goal=run_options.inherit_goal,
                effort=run_options.effort,
                permissions=run_options.permissions,
                provider=run_options.provider,
            )
        )
        try:
            async for event in session.stream(prompt, run_options):
                yield event
        finally:
            await session.close()

    def stream_sync(
        self,
        prompt: str,
        options: Any | None = None,
    ) -> tuple[Event, ...]:
        """Collect one streamed turn from synchronous code."""

        return run_blocking(lambda: collect_events(self.stream(prompt, options)))

    def _require_run_options(self, options: Any) -> Harness:
        """Return a harness whose surface satisfies run option requirements."""

        return self.require(
            *self._features_for_agent_and_options(options),
            channel=option_channel(options),
        )

    def _features_for_agent_and_options(self, options: Any | None) -> tuple[Any, ...]:
        """Return features implied by this harness's agent and options."""

        return unique_feature_values(
            (*self.agent.features(), *self._features_for_options(options))
        )

    def _features_for_options(self, options: Any | None) -> tuple[Any, ...]:
        """Return features implied by an option object."""

        if options is None or not hasattr(options, "features"):
            return ()
        return tuple(options.features(self.agent.goal, provider=self.provider))

    async def start(self, options: Any | None = None) -> Session:
        """Start or resume a provider session."""

        from yoke.adapters import adapter_for
        from yoke.options import SessionOptions

        session_options = (
            options
            if isinstance(options, SessionOptions)
            else SessionOptions.model_validate(options or {})
        )
        harness = self.require(
            *unique_feature_values(
                (
                    *self.agent.features(),
                    *session_options.features(
                        self.agent.goal,
                        provider=self.provider,
                    ),
                )
            ),
            channel=session_options.channel,
        )
        return await adapter_for(harness.provider, harness.surface).start(
            harness,
            session_options,
        )

    def start_sync(self, options: Any | None = None) -> Session:
        """Start or resume a provider session from synchronous code."""

        return run_blocking(lambda: self.start(options))

    async def goal_loop(self, options: Any) -> GoalRun:
        """Start a provider-owned keep-working goal loop."""

        from yoke.adapters import adapter_for
        from yoke.options import GoalLoopOptions

        if not isinstance(options, GoalLoopOptions):
            options = GoalLoopOptions.model_validate(options)
        harness = self.require(
            *options.features(self.agent.goal, provider=self.provider),
            channel=options.channel,
        )
        return await adapter_for(harness.provider, harness.surface).goal_loop(
            harness,
            options,
        )

    def goal_loop_sync(self, options: Any) -> GoalRun:
        """Start a provider-owned keep-working goal loop from synchronous code."""

        return run_blocking(lambda: self.goal_loop(options))

    def session(self, options: Any | None = None) -> SessionContext:
        """Return an async context manager that starts and closes a session."""

        return SessionContext(self, options)

    def session_sync(self, options: Any | None = None) -> SyncSessionContext:
        """Return a sync context manager that starts and closes a session."""

        return SyncSessionContext(self, options)

    async def check(self) -> Readiness:
        """Check local readiness for the selected provider surface."""

        from yoke.adapters import adapter_for

        return await adapter_for(self.provider, self.surface).check(self)

    def auth_methods(self) -> tuple[AuthMethod, ...]:
        """Return credential methods accepted by the selected surface."""

        if self.provider is Provider.CLAUDE:
            return (
                AuthMethod.EXTERNAL,
                AuthMethod.API_KEY,
                AuthMethod.OAUTH_TOKEN,
            )
        return (AuthMethod.EXTERNAL,)

    def login_methods(self) -> tuple[AuthMethod, ...]:
        """Return explicit provider-persisted login flows for this surface."""

        if self.provider is Provider.CODEX and self.surface == Surface.CODEX_PYTHON_SDK:
            return (
                AuthMethod.API_KEY,
                AuthMethod.CHATGPT,
                AuthMethod.DEVICE_CODE,
            )
        return ()

    async def auth_status(self) -> Authentication:
        """Inspect installation and authentication without starting a paid turn."""

        from yoke.adapters import adapter_for

        adapter = adapter_for(self.provider, self.surface)
        inspect_auth = getattr(adapter, "auth_status", None)
        if inspect_auth is not None:
            return await inspect_auth(self)
        readiness = await adapter.check(self)
        return Authentication(
            provider=self.provider,
            surface=self.surface or adapter.surface,
            methods=self.auth_methods(),
            method=None,
            installed=readiness.available,
            authenticated=None,
            compatible=None,
            ready=readiness.available,
            live_tested=False,
            message=readiness.message,
        )

    def auth_status_sync(self) -> Authentication:
        return run_blocking(lambda: self.auth_status())

    def check_sync(self) -> Readiness:
        """Check local readiness from synchronous code."""

        return run_blocking(lambda: self.check())

    async def status(self):
        """Return readiness plus declared capability metadata."""

        from yoke.status import Status

        return Status(readiness=await self.check(), report=self.report())

    def status_sync(self):
        """Return readiness and capability metadata from synchronous code."""

        return run_blocking(lambda: self.status())

    async def statuses(
        self,
        *,
        channel: Channel | str | None = None,
        runnable: bool | None = True,
    ) -> tuple[Any, ...]:
        """Return readiness plus capabilities for matching provider surfaces."""

        from yoke.surfaces import profiles_for

        effective_channel = first_present(channel, self.channel)
        if self.surface is not None:
            return (await self.require(channel=effective_channel).status(),)
        profiles = profiles_for(
            self.provider,
            channel=effective_channel,
            runnable=runnable,
        )
        statuses = []
        for profile in profiles:
            harness = self.model_copy(
                update={"surface": profile.surface, "channel": profile.channel}
            )
            statuses.append(await harness.status())
        return tuple(statuses)

    def statuses_sync(
        self,
        *,
        channel: Channel | str | None = None,
        runnable: bool | None = True,
    ) -> tuple[Any, ...]:
        """Return matching surface statuses from synchronous code."""

        return run_blocking(lambda: self.statuses(channel=channel, runnable=runnable))

    async def sessions(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        cwd: str | Path | None = None,
        include_worktrees: bool = True,
    ) -> SessionList:
        """List stored provider sessions/threads without starting a turn."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.SESSION_LIST)
        return await adapter_for(harness.provider, harness.surface).list_sessions(
            harness,
            limit=limit,
            cursor=cursor,
            cwd=cwd,
            include_worktrees=include_worktrees,
        )

    def sessions_sync(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        cwd: str | Path | None = None,
        include_worktrees: bool = True,
    ) -> SessionList:
        """List stored provider sessions/threads from synchronous code."""

        return run_blocking(
            lambda: self.sessions(
                limit=limit,
                cursor=cursor,
                cwd=cwd,
                include_worktrees=include_worktrees,
            )
        )

    async def read_session(
        self,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        """Read stored provider session/thread history without resuming it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.SESSION_READ)
        return await adapter_for(harness.provider, harness.surface).read_session(
            harness,
            session_id,
            include_messages=include_messages,
            limit=limit,
            offset=offset,
        )

    def read_session_sync(
        self,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        """Read stored provider session/thread history from synchronous code."""

        return run_blocking(
            lambda: self.read_session(
                session_id,
                include_messages=include_messages,
                limit=limit,
                offset=offset,
            )
        )

    async def rename_session(self, session_id: str, title: str) -> SessionSummary:
        """Rename a stored provider session/thread when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.SESSION_RENAME)
        session = Session(
            provider=harness.provider,
            surface=harness.surface,
            channel=harness.channel,
            id=session_id,
            provider_session_id=session_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=harness.permissions,
        )
        return await adapter_for(harness.provider, harness.surface).rename(
            session,
            title,
        )

    def rename_session_sync(self, session_id: str, title: str) -> SessionSummary:
        """Rename a stored provider session/thread from synchronous code."""

        return run_blocking(lambda: self.rename_session(session_id, title))

    async def tag_session(
        self,
        session_id: str,
        tag: str | None,
    ) -> SessionSummary:
        """Tag or untag a stored provider session when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.SESSION_TAG)
        session = Session(
            provider=harness.provider,
            surface=harness.surface,
            channel=harness.channel,
            id=session_id,
            provider_session_id=session_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=harness.permissions,
        )
        return await adapter_for(harness.provider, harness.surface).tag(
            session,
            tag,
        )

    def tag_session_sync(self, session_id: str, tag: str | None) -> SessionSummary:
        """Tag or untag a stored provider session from synchronous code."""

        return run_blocking(lambda: self.tag_session(session_id, tag))

    async def login(
        self,
        method: AuthMethod | str = AuthMethod.EXTERNAL,
        *,
        api_key: str | None = None,
    ) -> Login:
        """Start a provider-native login flow when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.LOGIN)
        return await adapter_for(harness.provider, harness.surface).login(
            harness,
            method,
            api_key=api_key,
        )

    def login_sync(
        self,
        method: AuthMethod | str = AuthMethod.EXTERNAL,
        *,
        api_key: str | None = None,
    ) -> Login:
        """Start a provider-native login flow from synchronous code."""

        return run_blocking(lambda: self.login(method, api_key=api_key))

    async def workflow(
        self,
        workflow: Workflow | str,
        prompt: Any = None,
        options: Any | None = None,
    ) -> WorkflowRun:
        """Run a Yoke workflow."""

        from yoke.options import WorkflowOptions
        from yoke.workflows import run_workflow

        workflow_options = (
            options
            if isinstance(options, WorkflowOptions)
            else WorkflowOptions.model_validate(options or {})
        )
        selected = (
            self.agent.workflows[workflow] if isinstance(workflow, str) else workflow
        )
        from yoke.workflows import workflow_features

        harness = self.require(
            *workflow_features(
                selected,
                workflow_options,
                self.agent,
                provider=self.provider,
            ),
            channel=workflow_options.channel,
        )
        return await run_workflow(harness, selected, prompt, workflow_options)

    def workflow_sync(
        self,
        workflow: Workflow | str,
        prompt: Any = None,
        options: Any | None = None,
    ) -> WorkflowRun:
        """Run a Yoke workflow from synchronous code."""

        return run_blocking(lambda: self.workflow(workflow, prompt, options))

    async def models(self) -> tuple[Model, ...]:
        """List provider models when the selected surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        harness = self.require(Feature.MODELS)
        return await adapter_for(harness.provider, harness.surface).models(harness)

    def models_sync(self) -> tuple[Model, ...]:
        """List provider models from synchronous code."""

        return run_blocking(lambda: self.models())

    def model_selection(self, options: Any | None = None) -> ModelSelection:
        """Explain where model selection comes from for this harness.

        This is local metadata. It does not call the provider or prove that the
        signed-in account can use a specific model. Use `models()` on surfaces
        with model-list support when you need live account data.
        """

        from yoke.capabilities import Feature

        profile = self.profile()
        model, source = self._selected_model(options)
        support = profile.support_for(Feature.MODELS)
        verifiable = profile.supports(Feature.MODELS)
        if model is None:
            note = (
                f"{profile.surface} will use the provider default model unless "
                "provider-specific options override it."
            )
        elif verifiable:
            note = (
                f"Yoke will pass model {model!r} to {profile.surface}. "
                "Call models() to compare it with account-supported models."
            )
        else:
            note = (
                f"Yoke will pass model {model!r} to {profile.surface}, but this "
                "surface does not expose model listing through Yoke, so account "
                "support is provider-validated at run time."
            )
        return ModelSelection(
            model=model,
            source=source,
            provider=profile.provider,
            surface=profile.surface,
            channel=profile.channel,
            model_listing=str(support),
            verifiable=verifiable,
            note=note,
        )

    def _selected_model(self, options: Any | None) -> tuple[str | None, ModelSource]:
        """Return the requested model and where it was configured."""

        model = getattr(options, "model", None)
        if model is not None:
            if options.__class__.__name__ == "SessionOptions":
                return str(model), ModelSource.SESSION
            return str(model), ModelSource.RUN
        if self.agent.model is not None:
            return self.agent.model, ModelSource.AGENT
        return None, ModelSource.PROVIDER_DEFAULT

    def capabilities(self):
        """Return the selected provider surface capability matrix."""

        from yoke.adapters import adapter_for

        return adapter_for(self.provider, self.surface).capabilities

    def profile(self):
        """Return the selected provider surface profile."""

        from yoke.surfaces import profile_for

        return profile_for(self.provider, self.surface)

    def report(self):
        """Return a JSON-friendly selected surface capability report."""

        from yoke.surfaces import report_for

        return report_for(self.provider, self.surface)

    def fit(self, *features: Any):
        """Return how the selected surface fits requested features."""

        from yoke.capabilities import Feature
        from yoke.surfaces import fit_profile

        required = tuple(Feature(feature) for feature in features)
        return fit_profile(self.profile(), required)

    def fits(
        self,
        *features: Any,
        channel: Channel | str | None = None,
        runnable: bool | None = True,
    ):
        """Return ranked provider-surface fits for requested features."""

        from yoke.surfaces import fits_for

        return fits_for(
            self.provider,
            requires=features,
            channel=channel,
            runnable=runnable,
        )


class Session(YokeModel):
    """Runtime session handle.

    `Session` is serializable enough to resume simple providers, but adapters
    may keep live provider state behind the handle.
    """

    provider: Provider
    surface: Surface | str | None = None
    channel: Channel | None = None
    id: str
    provider_session_id: str | None = None
    agent: Agent | None = None
    cwd: Path | None = None
    permissions: Permissions | None = None
    goal: Goal | None = None
    model: str | None = None
    runtime_root: Path | None = Field(default=None, exclude=True, repr=False)
    credentials: Credentials = Field(
        default_factory=Credentials.auto, exclude=True, repr=False
    )

    def __init__(self, provider: Provider | str | None = None, **data: Any):
        if provider is not None:
            data["provider"] = provider
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def normalize_surface_alias(cls, data: object) -> object:
        if isinstance(data, dict):
            provider, surface = split_provider_surface(
                data.get("provider"),
                data.get("surface"),
            )
            return {
                **data,
                "provider": provider,
                "surface": normalize_provider_surface(provider, surface),
            }
        return data

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    async def __aenter__(self) -> Session:
        """Enter an async session context."""

        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the provider session when leaving an async context."""

        await self.close()

    def __enter__(self) -> Session:
        """Enter a sync session context."""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the provider session when leaving a sync context."""

        self.close_sync()

    def require(
        self,
        *features: Any,
        channel: Channel | str | None = None,
        runnable: bool = True,
    ) -> Session:
        """Return a session whose surface satisfies the requested features."""

        effective_channel = channel if channel is not None else self.channel
        if not features and effective_channel is None:
            return self
        plan = surface_plan(
            provider=self.provider,
            surface=self.surface,
            features=features,
            channel=effective_channel,
            runnable=runnable,
        ).raise_for_status()
        if self.surface is None:
            return self.model_copy(update={"surface": plan.profile.surface})
        return self

    def plan(
        self,
        options: Any | None = None,
        *,
        features: tuple[Any, ...] = (),
        channel: Channel | str | None = None,
        runnable: bool = True,
    ):
        """Return the surface plan Yoke would use for these requirements."""

        effective_channel = first_present(
            channel,
            option_channel(options),
            self.channel,
        )
        required = self._features_for_agent_and_options(options)
        required = (*required, *features)
        return surface_plan(
            provider=self.provider,
            surface=self.surface,
            features=required,
            channel=effective_channel,
            runnable=runnable,
        )

    async def run(self, prompt: str, options: Any | None = None) -> Run:
        """Send one turn and collect the result."""

        from yoke.adapters import adapter_for
        from yoke.options import RunOptions

        run_options = options if isinstance(options, RunOptions) else RunOptions()
        session = self._require_run_options(run_options)
        return await adapter_for(session.provider, session.surface).send(
            session,
            Turn(prompt=prompt),
            run_options,
        )

    def run_sync(self, prompt: str, options: Any | None = None) -> Run:
        """Send one turn from synchronous code."""

        return run_blocking(lambda: self.run(prompt, options))

    async def stream(
        self,
        prompt: str,
        options: Any | None = None,
    ) -> AsyncIterator[Event]:
        """Send one turn and stream normalized events."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature
        from yoke.options import RunOptions

        run_options = options if isinstance(options, RunOptions) else RunOptions()
        session = self.require(
            Feature.STREAMING,
            *self._features_for_agent_and_options(run_options),
            channel=run_options.channel,
        )
        async for event in adapter_for(session.provider, session.surface).stream(
            session,
            Turn(prompt=prompt),
            run_options,
        ):
            yield event

    def stream_sync(
        self,
        prompt: str,
        options: Any | None = None,
    ) -> tuple[Event, ...]:
        """Collect stream events from synchronous code."""

        return run_blocking(lambda: collect_events(self.stream(prompt, options)))

    def _require_run_options(self, options: Any) -> Session:
        """Return a session whose surface satisfies run option requirements."""

        return self.require(
            *self._features_for_agent_and_options(options),
            channel=option_channel(options),
        )

    def _features_for_agent_and_options(self, options: Any | None) -> tuple[Any, ...]:
        """Return features implied by this session's agent and options."""

        agent_features = self.agent.features() if self.agent is not None else ()
        return unique_feature_values(
            (*agent_features, *self._features_for_options(options))
        )

    def _features_for_options(self, options: Any | None) -> tuple[Any, ...]:
        """Return features implied by an option object."""

        if options is None or not hasattr(options, "features"):
            return ()
        return tuple(options.features(self.goal, provider=self.provider))

    async def get_goal(self) -> Goal | None:
        """Read provider goal state when supported."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.READABLE_GOAL)
        return await adapter_for(session.provider, session.surface).get_goal(session)

    def get_goal_sync(self) -> Goal | None:
        """Read provider goal state from synchronous code."""

        return run_blocking(lambda: self.get_goal())

    async def set_goal(self, goal: Goal) -> Session:
        """Attach or update a provider goal and return the updated session."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.MUTABLE_GOAL)
        return await adapter_for(session.provider, session.surface).set_goal(
            session,
            goal,
        )

    def set_goal_sync(self, goal: Goal) -> Session:
        """Attach or update a provider goal from synchronous code."""

        return run_blocking(lambda: self.set_goal(goal))

    async def clear_goal(self) -> Session:
        """Clear provider goal state and return the updated session."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.MUTABLE_GOAL)
        return await adapter_for(session.provider, session.surface).clear_goal(session)

    def clear_goal_sync(self) -> Session:
        """Clear provider goal state from synchronous code."""

        return run_blocking(lambda: self.clear_goal())

    async def interrupt(self) -> None:
        """Request interruption of the active provider turn when supported."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.INTERRUPT)
        await adapter_for(session.provider, session.surface).interrupt(session)

    def interrupt_sync(self) -> None:
        """Request interruption of the active provider turn from sync code."""

        return run_blocking(lambda: self.interrupt())

    async def compact(self) -> None:
        """Request provider-native compaction of this session when supported."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.SESSION_COMPACT)
        await adapter_for(session.provider, session.surface).compact(session)

    def compact_sync(self) -> None:
        """Request provider-native compaction of this session from sync code."""

        return run_blocking(lambda: self.compact())

    async def rename(self, title: str) -> SessionSummary:
        """Rename this provider session when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.SESSION_RENAME)
        return await adapter_for(session.provider, session.surface).rename(
            session,
            title,
        )

    def rename_sync(self, title: str) -> SessionSummary:
        """Rename this provider session from synchronous code."""

        return run_blocking(lambda: self.rename(title))

    async def tag(self, tag: str | None) -> SessionSummary:
        """Tag or untag this provider session when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature

        session = self.require(Feature.SESSION_TAG)
        return await adapter_for(session.provider, session.surface).tag(session, tag)

    def tag_sync(self, tag: str | None) -> SessionSummary:
        """Tag or untag this provider session from synchronous code."""

        return run_blocking(lambda: self.tag(tag))

    async def fork(self, options: Any | None = None) -> Session:
        """Branch this provider session when the surface supports it."""

        from yoke.adapters import adapter_for
        from yoke.capabilities import Feature
        from yoke.options import ForkOptions

        fork_options = options if isinstance(options, ForkOptions) else ForkOptions()
        session = self.require(Feature.FORK)
        return await adapter_for(session.provider, session.surface).fork(
            session,
            fork_options,
        )

    def fork_sync(self, options: Any | None = None) -> Session:
        """Branch this provider session from synchronous code."""

        return run_blocking(lambda: self.fork(options))

    async def close(self) -> None:
        """Release provider resources for this session."""

        from yoke.adapters import adapter_for

        await adapter_for(self.provider, self.surface).close(self)

    def close_sync(self) -> None:
        """Release provider resources from synchronous code."""

        return run_blocking(lambda: self.close())

    def capabilities(self):
        """Return the selected provider surface capability matrix."""

        from yoke.adapters import adapter_for

        return adapter_for(self.provider, self.surface).capabilities

    def profile(self):
        """Return the selected provider surface profile."""

        from yoke.surfaces import profile_for

        return profile_for(self.provider, self.surface)

    def report(self):
        """Return a JSON-friendly selected surface capability report."""

        from yoke.surfaces import report_for

        return report_for(self.provider, self.surface)

    def fit(self, *features: Any):
        """Return how the selected surface fits requested features."""

        from yoke.capabilities import Feature
        from yoke.surfaces import fit_profile

        required = tuple(Feature(feature) for feature in features)
        return fit_profile(self.profile(), required)

    def fits(
        self,
        *features: Any,
        channel: Channel | str | None = None,
        runnable: bool | None = True,
    ):
        """Return ranked provider-surface fits for requested features."""

        from yoke.surfaces import fits_for

        return fits_for(
            self.provider,
            requires=features,
            channel=channel,
            runnable=runnable,
        )


class SessionContext:
    """Async context manager returned by `Harness.session()`."""

    def __init__(self, harness: Harness, options: Any | None = None) -> None:
        self.harness = harness
        self.options = options
        self._session: Session | None = None

    async def __aenter__(self) -> Session:
        self._session = await self.harness.start(self.options)
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is not None:
            await self._session.close()


class SyncSessionContext:
    """Sync context manager returned by `Harness.session_sync()`."""

    def __init__(self, harness: Harness, options: Any | None = None) -> None:
        self.harness = harness
        self.options = options
        self._session: Session | None = None

    def __enter__(self) -> Session:
        self._session = self.harness.start_sync(self.options)
        return self._session

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is not None:
            self._session.close_sync()


class Turn(YokeModel):
    """One input turn inside a session."""

    prompt: str
    id: str | None = None
    model: str | None = None


class Tool(YokeModel):
    """Display metadata for one provider tool item."""

    kind: ToolKind = ToolKind.UNKNOWN
    title: str | None = None
    path: str | None = None
    command: str | None = None
    cwd: str | None = None
    status: ToolStatus | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    summary: str | None = None


class Usage(YokeModel):
    """Token usage reported by a provider."""

    input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    total_tokens: int | None = None
    total_processed_tokens: int | None = None
    max_tokens: int | None = None


class AgentCall(YokeModel):
    """Provider-native agent or collaboration tool activity."""

    action: str | None = None
    agent_id: str | None = None
    agent_type: str | None = None
    sender_thread_id: str | None = None
    receiver_thread_ids: tuple[str, ...] = ()
    new_thread_id: str | None = None
    prompt: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    states: object | None = None


class Response(YokeModel):
    """Answer returned to a provider request."""

    result: Any | None = None
    error: Any | None = None
    decision: str | None = None
    message: str | None = None
    answers: dict[str, Any] | None = None
    updated_input: Any | None = None
    updated_permissions: Any | None = None
    interrupt: bool = False
    raw: object | None = None

    @classmethod
    def allow(
        cls,
        updated_input: Any | None = None,
        *,
        answers: dict[str, Any] | None = None,
        updated_permissions: Any | None = None,
    ) -> Response:
        """Create an allow response for callback-style providers."""

        return cls(
            decision="allow",
            answers=answers,
            updated_input=updated_input,
            updated_permissions=updated_permissions,
        )

    @classmethod
    def deny(
        cls,
        message: str = "Denied by Yoke.",
        *,
        interrupt: bool = False,
    ) -> Response:
        """Create a deny response for callback-style providers."""

        return cls(decision="deny", message=message, interrupt=interrupt)


class Request(YokeModel):
    """Structured provider request attached to an event."""

    kind: RequestKind | str
    id: str | None = None
    method: str | None = None
    message: str | None = None
    tool: Tool | None = None
    input: Any | None = None
    default: Response | None = None
    raw: object | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_known_kind(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return RequestKind(value)
            except ValueError:
                return value
        return value


class Event(YokeModel):
    """Normalized provider event."""

    kind: EventKind | str
    surface: Surface | str | None = None
    message: str | None = None
    tool_id: str | None = None
    tool_name: str | None = None
    tool_input: str | None = None
    tool: Tool | None = None
    tool_result: Any | None = None
    tool_is_error: bool | None = None
    agent: AgentCall | None = None
    request: Request | None = None
    response: Response | None = None
    goal: Goal | None = None
    usage: Usage | None = None
    provider_session_id: str | None = None
    provider_event_id: str | None = None
    provider_parent_tool_use_id: str | None = None
    source_thread_id: str | None = None
    source_turn_id: str | None = None
    raw: object | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_known_kind(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return EventKind(value)
            except ValueError:
                return value
        return value

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    @property
    def text(self) -> str | None:
        """Readable alias for display text carried by this event."""

        return self.message


class Run(YokeModel):
    """Convenience result for a one-shot run."""

    provider: Provider
    surface: Surface | str | None = None
    status: RunStatus = RunStatus.SUCCEEDED
    output: str | None = None
    data: Any | None = None
    events: tuple[Event, ...] = ()
    session: Session | None = None
    usage: Usage | dict[str, Any] | None = None
    failure: Failure | None = None
    requested_model: str | None = None

    @field_validator("surface", mode="before")
    @classmethod
    def normalize_known_surface(cls, value: object) -> object:
        return normalize_surface(value)

    @property
    def ok(self) -> bool:
        """Whether the run succeeded."""

        return self.status == RunStatus.SUCCEEDED

    def raise_for_status(self) -> Run:
        """Raise if the run failed, otherwise return this result."""

        if self.ok:
            return self
        raise_status_error("run", self.failure, self.output)

    @computed_field
    @property
    def provider_session_id(self) -> str | None:
        """Return the provider-native session id learned during this run."""

        if self.session is not None and self.session.provider_session_id is not None:
            return self.session.provider_session_id
        for event in reversed(self.events):
            if event.provider_session_id is not None:
                return event.provider_session_id
        return None


def raise_status_error(kind: str, failure: Failure | None, output: str | None) -> None:
    """Raise a YokeError for a failed result."""

    from yoke.errors import YokeError

    if failure is not None:
        code = f" [{failure.code}]" if failure.code else ""
        raise YokeError(f"{kind} failed{code}: {failure.message}")
    if output:
        raise YokeError(f"{kind} failed: {output}")
    raise YokeError(f"{kind} failed")


def first_present(*values: Any) -> Any:
    """Return the first value that is not None."""

    for value in values:
        if value is not None:
            return value
    return None


def option_channel(options: Any | None) -> Channel | str | None:
    """Return channel metadata carried by an option object."""

    if options is None:
        return None
    return getattr(options, "channel", None)


def surface_plan(
    *,
    provider: Provider,
    surface: Surface | str | None,
    features: tuple[Any, ...],
    channel: Channel | str | None,
    runnable: bool,
):
    """Return a Plan for the given provider surface requirements."""

    from yoke.capabilities import Feature, Plan
    from yoke.surfaces import fit_profile, fits_for, profile_for, select_profile

    required = unique_features(features)
    channel_value = Channel(channel) if channel is not None else None
    candidates = fits_for(
        provider,
        requires=required,
        channel=channel_value,
        runnable=runnable,
    )
    profile = profile_for(provider, surface)
    channel_mismatch = (
        surface is not None
        and channel_value is not None
        and profile.channel is not channel_value
    )
    if (
        surface is None
        and required
        and required != (Feature.GOAL,)
    ):
        profile = select_profile(
            provider,
            requires=required,
            channel=channel_value,
            runnable=runnable,
        )
    elif surface is None and required and not profile.supports_all(required):
        profile = select_profile(
            provider,
            requires=required,
            channel=channel_value,
            runnable=runnable,
        )
    elif surface is None and channel_value is not None:
        profile = select_profile(provider, channel=channel_value, runnable=runnable)
    return Plan(
        features=required,
        channel=channel_value,
        channel_mismatch=channel_mismatch,
        fit=fit_profile(profile, required),
        candidates=candidates,
    )


def unique_features(features: tuple[Any, ...]):
    """Normalize feature values while preserving first-seen order."""

    from yoke.capabilities import Feature

    return tuple(Feature(feature) for feature in unique_feature_values(features))


def unique_feature_values(features: tuple[Any, ...]) -> tuple[Any, ...]:
    """Deduplicate feature-like values while preserving first-seen order."""

    from yoke.capabilities import Feature

    required: list[Feature] = []
    for feature in features:
        value = Feature(feature)
        if value not in required:
            required.append(value)
    return tuple(required)
