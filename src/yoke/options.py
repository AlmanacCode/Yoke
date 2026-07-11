"""Run-time options that live beside, not inside, agent definitions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

from yoke.models import Channel, Effort, Event, Goal, Permissions, YokeModel
from yoke.policies import RequestPolicy
from yoke.replay import WorkflowReplay
from yoke.structured import OutputSchema

if TYPE_CHECKING:
    from yoke.capabilities import Feature


class RuntimeOption(YokeModel):
    """An option value that only exists in the live SDK object graph."""

    path: str
    reason: str


class CodexAppServerExposure(YokeModel):
    """How Codex app-server options enter the provider surface."""

    stable: tuple[str, ...] = ()
    experimental: tuple[str, ...] = ()
    runtime: tuple[RuntimeOption, ...] = ()


def runtime_options(value: object, prefix: str = "") -> tuple[RuntimeOption, ...]:
    """Return active runtime-only option fields inside a model tree."""

    if isinstance(value, BaseModel):
        options: list[RuntimeOption] = []
        for name, field in value.__class__.model_fields.items():
            path = f"{prefix}.{name}" if prefix else name
            field_value = getattr(value, name, None)
            extra = field.json_schema_extra
            metadata = extra if isinstance(extra, dict) else {}
            if metadata.get("runtime_only") and field_value is not None:
                options.append(
                    RuntimeOption(
                        path=path,
                        reason=str(
                            metadata.get(
                                "reason",
                                "This option cannot be represented in a folder.",
                            )
                        ),
                    )
                )
                continue
            options.extend(runtime_options(field_value, path))
        return tuple(options)
    if callable(value):
        return (
            RuntimeOption(
                path=prefix or "value",
                reason=(
                    "Callables are live Python objects. Configure this value in "
                    "SDK code, not in a Yoke folder."
                ),
            ),
        )
    if isinstance(value, dict):
        options: list[RuntimeOption] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            options.extend(runtime_options(item, path))
        return tuple(options)
    if isinstance(value, tuple | list):
        options: list[RuntimeOption] = []
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            options.extend(runtime_options(item, path))
        return tuple(options)
    return ()


class RunOptions(YokeModel):
    """Options for one convenience run."""

    channel: Channel | str | None = None
    model: str | None = None
    effort: Effort | str | None = None
    goal: Goal | None = None
    inherit_goal: bool = True
    output_schema: OutputSchema | None = None
    max_turns: int | None = None
    timeout_seconds: float | None = None
    permissions: Permissions | None = None
    provider: ProviderOptions | None = None
    on_event: Callable[[Event], None] | None = Field(
        default=None,
        exclude=True,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Run event callbacks are live Python objects and do not "
                "round-trip through folders."
            ),
        },
    )

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    @field_validator("timeout_seconds")
    @classmethod
    def require_positive_timeout(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("run timeout must be greater than zero")
        return value

    def resolve_goal(self, agent_goal: Goal | None) -> Goal | None:
        """Return the explicit goal or the inherited agent goal."""

        if self.goal is not None:
            return self.goal
        if self.inherit_goal:
            return agent_goal
        return None

    def features(
        self,
        inherited_goal: Goal | None = None,
        *,
        provider: object | None = None,
    ) -> tuple[Feature, ...]:
        """Return provider features implied by these run options."""

        from yoke.capabilities import Feature

        features: list[Feature] = []
        if self.resolve_goal(inherited_goal) is not None:
            features.append(Feature.GOAL)
        if self.output_schema is not None:
            features.append(Feature.STRUCTURED_OUTPUT)
        if self.on_event is not None:
            features.append(Feature.RUN_EVENT_CALLBACKS)
        if self.provider is not None:
            extend_unique(features, self.provider.features(provider=provider))
        return tuple(features)


class SessionOptions(YokeModel):
    """Options for starting or resuming a session."""

    channel: Channel | str | None = None
    model: str | None = None
    goal: Goal | None = None
    inherit_goal: bool = True
    effort: Effort | str | None = None
    permissions: Permissions | None = None
    resume: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    provider: ProviderOptions | None = None

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    def resolve_goal(self, agent_goal: Goal | None) -> Goal | None:
        """Return the explicit goal or the inherited agent goal."""

        if self.goal is not None:
            return self.goal
        if self.inherit_goal:
            return agent_goal
        return None

    def features(
        self,
        inherited_goal: Goal | None = None,
        *,
        provider: object | None = None,
    ) -> tuple[Feature, ...]:
        """Return provider features implied by these session options."""

        from yoke.capabilities import Feature

        features: list[Feature] = [Feature.SESSION]
        if self.resolve_goal(inherited_goal) is not None:
            features.append(Feature.GOAL)
        if self.provider is not None:
            extend_unique(features, self.provider.features(provider=provider))
        return tuple(features)


class ForkOptions(YokeModel):
    """Options for branching a provider session."""

    ephemeral: bool = False
    last_turn_id: str | None = None
    exclude_turns: bool | None = None


class GoalLoopOptions(YokeModel):
    """Options for provider-native goal loops that can continue beyond one turn."""

    goal: Goal
    channel: Channel | str | None = None

    def features(
        self,
        inherited_goal: Goal | None = None,
        *,
        provider: object | None = None,
    ) -> tuple[Feature, ...]:
        """Return provider features implied by a keep-working goal loop."""

        from yoke.capabilities import Feature

        return (Feature.GOAL_LOOP,)


class WorkflowOptions(YokeModel):
    """Options for workflow orchestration."""

    channel: Channel | str | None = None
    concurrency: int = 4
    fail_fast: bool = True
    native: bool = False
    resume: str | None = None
    memory: WorkflowReplay | None = Field(
        default=None,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Workflow replay stores live Run objects and does not "
                "round-trip."
            ),
        },
    )
    run: RunOptions = Field(default_factory=RunOptions)
    output_schema: OutputSchema | None = None
    timeout_seconds: float | None = None
    step_timeout_seconds: float | None = None
    on_event: Callable[[Any], object] | None = Field(
        default=None,
        exclude=True,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Workflow event callbacks are live Python objects and do not "
                "round-trip through folders."
            ),
        },
    )

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    @field_validator("concurrency")
    @classmethod
    def require_positive_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("workflow concurrency must be at least 1")
        return value

    @field_validator("timeout_seconds", "step_timeout_seconds")
    @classmethod
    def require_positive_timeout(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("workflow timeouts must be greater than zero")
        return value

    def features(
        self,
        inherited_goal: Goal | None = None,
        *,
        provider: object | None = None,
    ) -> tuple[Feature, ...]:
        """Return provider features implied by workflow execution."""

        from yoke.capabilities import Feature

        features: list[Feature] = [Feature.WORKFLOW]
        if self.native:
            features.append(Feature.NATIVE_WORKFLOW)
        if self.output_schema is not None:
            features.append(Feature.STRUCTURED_OUTPUT)
        for feature in self.run.features(inherited_goal, provider=provider):
            if feature not in features:
                features.append(feature)
        return tuple(features)


class ClaudePermissionMode(StrEnum):
    """Claude Agent SDK permission modes."""

    DEFAULT = "default"
    DONT_ASK = "dontAsk"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    PLAN = "plan"
    AUTO = "auto"


class ClaudeToolsPreset(StrEnum):
    """Claude Agent SDK top-level tool presets."""

    CLAUDE_CODE = "claude_code"


class ClaudeToolset(YokeModel):
    """Claude Agent SDK preset for the base available toolset."""

    type: Literal["preset"] = "preset"
    preset: ClaudeToolsPreset | str = ClaudeToolsPreset.CLAUDE_CODE


class HookEvent(StrEnum):
    """Claude hook event names supported by the Agent SDK."""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    NOTIFICATION = "Notification"
    SUBAGENT_START = "SubagentStart"
    PERMISSION_REQUEST = "PermissionRequest"


class Hook(YokeModel):
    """Runtime hook callback bound to a provider hook event."""

    event: HookEvent | str
    matcher: str | None = None
    callbacks: tuple[Any, ...] = Field(
        default=(),
        exclude=True,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Hook callbacks are live Python callables. Configure callbacks "
                "in SDK code, not in a Yoke folder."
            ),
        },
    )
    timeout: float | None = None

    def __init__(self, event: HookEvent | str | None = None, **data: Any):
        if event is not None:
            data["event"] = event
        super().__init__(**data)


class ClaudeOptions(YokeModel):
    """Typed Claude options plus raw escape hatch."""

    tools: tuple[str, ...] | ClaudeToolset | dict[str, Any] | None = None
    setting_sources: tuple[str, ...] | None = None
    include_partial_messages: bool | None = None
    include_hook_events: bool | None = None
    max_budget_usd: float | None = None
    permission_mode: ClaudePermissionMode | str | None = Field(
        default=None,
        validation_alias=AliasChoices("permission_mode", "permissionMode"),
    )
    allowed_tools: tuple[str, ...] | None = Field(
        default=None,
        validation_alias=AliasChoices("allowed_tools", "allowedTools"),
    )
    disallowed_tools: tuple[str, ...] | None = Field(
        default=None,
        validation_alias=AliasChoices("disallowed_tools", "disallowedTools"),
    )
    can_use_tool: Any | None = Field(
        default=None,
        exclude=True,
        validation_alias=AliasChoices("can_use_tool", "canUseTool"),
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Claude canUseTool callbacks are live Python objects. Configure "
                "can_use_tool in SDK code, not in a Yoke folder."
            ),
        },
    )
    request_handler: Any | None = Field(
        default=None,
        exclude=True,
        validation_alias=AliasChoices("request_handler", "requestHandler"),
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Claude request handlers are live Python callbacks. Configure "
                "request_handler in SDK code, not in a Yoke folder."
            ),
        },
    )
    policy: RequestPolicy | dict[str, Any] | None = None
    hooks: Any | None = Field(
        default=None,
        exclude=True,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Claude hooks can contain live Python callbacks. Configure hooks "
                "in SDK code, not in a Yoke folder."
            ),
        },
    )
    agents: dict[str, ClaudeAgentOptions | dict[str, Any]] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)

    def features(self) -> tuple[Feature, ...]:
        """Return provider features implied by Claude options."""

        from yoke.capabilities import Feature

        features: list[Feature] = []
        if (
            self.tools is not None
            or self.raw.get("tools") is not None
            or self.raw.get("toolsPreset") is not None
            or self.raw.get("tools_preset") is not None
            or
            self.permission_mode is not None
            or self.allowed_tools is not None
            or self.disallowed_tools is not None
            or self.can_use_tool is not None
            or self.request_handler is not None
            or self.policy is not None
            or self.hooks is not None
            or self.raw.get("permission_mode") is not None
            or self.raw.get("permissionMode") is not None
            or self.raw.get("allowed_tools") is not None
            or self.raw.get("allowedTools") is not None
            or self.raw.get("disallowed_tools") is not None
            or self.raw.get("disallowedTools") is not None
            or self.raw.get("can_use_tool") is not None
            or self.raw.get("canUseTool") is not None
            or self.raw.get("request_handler") is not None
            or self.raw.get("requestHandler") is not None
            or self.raw.get("hooks") is not None
        ):
            features.append(Feature.CLAUDE_PERMISSIONS)
        if (
            self.can_use_tool is not None
            or self.request_handler is not None
            or self.policy is not None
            or self.raw.get("can_use_tool") is not None
            or self.raw.get("canUseTool") is not None
            or self.raw.get("request_handler") is not None
            or self.raw.get("requestHandler") is not None
        ):
            features.append(Feature.REQUEST_CALLBACKS)
        return tuple(features)


class ClaudeAgentOptions(YokeModel):
    """Claude AgentDefinition provider-specific overrides."""

    tools: tuple[str, ...] | None = None
    disallowed_tools: tuple[str, ...] | None = Field(
        default=None,
        validation_alias=AliasChoices("disallowed_tools", "disallowedTools"),
    )
    model: str | None = None
    skills: tuple[str, ...] | None = None
    memory: str | None = None
    mcp_servers: tuple[Any, ...] | None = Field(
        default=None,
        validation_alias=AliasChoices("mcp_servers", "mcpServers"),
    )
    initial_prompt: str | None = Field(
        default=None,
        validation_alias=AliasChoices("initial_prompt", "initialPrompt"),
    )
    max_turns: int | None = Field(
        default=None,
        validation_alias=AliasChoices("max_turns", "maxTurns"),
    )
    background: bool | None = None
    effort: Effort | str | int | None = None
    permission_mode: ClaudePermissionMode | str | None = Field(
        default=None,
        validation_alias=AliasChoices("permission_mode", "permissionMode"),
    )
    raw: dict[str, Any] = Field(default_factory=dict)

    def wire(self) -> dict[str, Any]:
        """Return AgentDefinition keyword arguments."""

        data = self.model_dump(exclude_none=True, exclude={"raw"})
        data.update(
            {key: value for key, value in self.raw.items() if value is not None}
        )
        return data


class CodexSandbox(StrEnum):
    """Codex sandbox modes."""

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


class CodexApproval(StrEnum):
    """Codex approval policies."""

    NEVER = "never"
    UNTRUSTED = "untrusted"
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"


class CodexReviewer(StrEnum):
    """Codex approval reviewers."""

    USER = "user"
    AUTO_REVIEW = "auto_review"


class CodexOptions(YokeModel):
    """Typed Codex options plus raw escape hatch."""

    experimental_api: bool = Field(
        default=False,
        validation_alias=AliasChoices("experimental_api", "experimentalApi"),
    )
    app_server: CodexAppServerOptions | dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("app_server", "appServer"),
    )
    collaboration: Collaboration | dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "collaboration",
            "collaboration_mode",
            "collaborationMode",
        ),
    )
    sandbox: CodexSandbox | str | None = None
    approval: CodexApproval | str | None = Field(
        default=None,
        validation_alias=AliasChoices("approval", "approval_policy", "approvalPolicy"),
    )
    approvals_reviewer: CodexReviewer | str | None = Field(
        default=None,
        validation_alias=AliasChoices("approvals_reviewer", "approvalsReviewer"),
    )
    permissions: str | dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "permissions",
            "permission_profile",
            "permissionProfile",
        ),
    )
    runtime_workspace_roots: tuple[str, ...] = Field(
        default=(),
        validation_alias=AliasChoices(
            "runtime_workspace_roots",
            "runtimeWorkspaceRoots",
        ),
    )
    environments: tuple[dict[str, Any], ...] | None = None
    selected_capability_roots: tuple[dict[str, Any], ...] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "selected_capability_roots",
            "selectedCapabilityRoots",
        ),
    )
    allow_provider_model_fallback: bool | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "allow_provider_model_fallback",
            "allowProviderModelFallback",
        ),
    )
    service_tier: str | None = Field(
        default=None,
        validation_alias=AliasChoices("service_tier", "serviceTier"),
    )
    client_user_message_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "client_user_message_id",
            "clientUserMessageId",
        ),
    )
    network: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("network", "network_access", "networkAccess"),
    )
    writable_roots: tuple[str, ...] = Field(
        default=(),
        validation_alias=AliasChoices("writable_roots", "writableRoots"),
    )
    raw: dict[str, Any] = Field(default_factory=dict)

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    def app_server_exposure(self) -> CodexAppServerExposure:
        """Return how app-server options enter the Codex protocol surface."""

        options = codex_app_server_options(self.app_server)
        return options.exposure(experimental_api=self.experimental_api)

    def features(self) -> tuple[Feature, ...]:
        """Return provider features implied by Codex options."""

        from yoke.capabilities import Feature

        features: list[Feature] = []
        if self.experimental_api or self.has_app_server_experimental_fields():
            features.append(Feature.EXPERIMENTAL_API)
        if self.collaboration is not None:
            features.append(Feature.COLLABORATION_MODE)
        if self.has_native_permissions():
            features.append(Feature.CODEX_PERMISSIONS)
        if self.raw.get("collaboration_mode") is not None:
            features.append(Feature.COLLABORATION_MODE)
        if self.raw.get("collaborationMode") is not None:
            features.append(Feature.COLLABORATION_MODE)
        if self.raw.get("experimental_api") is True:
            features.append(Feature.EXPERIMENTAL_API)
        if self.raw.get("experimentalApi") is True:
            features.append(Feature.EXPERIMENTAL_API)
        if codex_app_server_requests_present(self.app_server):
            features.append(Feature.REQUEST_EVENTS)
        raw_app_server = self.raw.get("app_server", self.raw.get("appServer"))
        if codex_app_server_requests_present(raw_app_server):
            features.append(Feature.REQUEST_EVENTS)
        deduped: list[Feature] = []
        extend_unique(deduped, tuple(features))
        return tuple(deduped)

    def has_native_permissions(self) -> bool:
        """Return whether Codex native permission controls are configured."""

        return (
            self.sandbox is not None
            or self.approval is not None
            or self.approvals_reviewer is not None
            or self.permissions is not None
            or self.network is not None
            or bool(self.writable_roots)
            or self.raw.get("sandbox") is not None
            or self.raw.get("approval") is not None
            or self.raw.get("approval_policy") is not None
            or self.raw.get("approvalPolicy") is not None
            or self.raw.get("approvals_reviewer") is not None
            or self.raw.get("approvalsReviewer") is not None
            or self.raw.get("permissions") is not None
            or self.raw.get("permission_profile") is not None
            or self.raw.get("permissionProfile") is not None
            or self.raw.get("network") is not None
            or self.raw.get("network_access") is not None
            or self.raw.get("networkAccess") is not None
            or self.raw.get("writable_roots") is not None
            or self.raw.get("writableRoots") is not None
        )

    def has_app_server_experimental_fields(self) -> bool:
        """Return whether experimental app-server fields are configured."""

        return (
            self.permissions is not None
            or bool(self.runtime_workspace_roots)
            or self.environments is not None
            or self.selected_capability_roots is not None
            or self.allow_provider_model_fallback is not None
            or self.raw.get("permissions") is not None
            or self.raw.get("permission_profile") is not None
            or self.raw.get("permissionProfile") is not None
            or self.raw.get("runtime_workspace_roots") is not None
            or self.raw.get("runtimeWorkspaceRoots") is not None
            or self.raw.get("environments") is not None
            or self.raw.get("selected_capability_roots") is not None
            or self.raw.get("selectedCapabilityRoots") is not None
            or self.raw.get("allow_provider_model_fallback") is not None
            or self.raw.get("allowProviderModelFallback") is not None
        )


class Collaboration(YokeModel):
    """Codex app-server collaboration mode."""

    mode: Literal["default", "plan"] | str = "default"
    settings: CollaborationSettings | dict[str, Any] = Field(
        default_factory=lambda: CollaborationSettings()
    )

    def wire(self) -> dict[str, Any]:
        """Return the app-server JSON-RPC shape."""

        settings = (
            self.settings.wire()
            if isinstance(self.settings, CollaborationSettings)
            else dict(self.settings)
        )
        return {"mode": self.mode, "settings": settings}


class CollaborationSettings(YokeModel):
    """Settings for a Codex app-server collaboration mode."""

    developer_instructions: str | None = None
    model: str | None = None
    reasoning_effort: Effort | str | None = None

    def wire(self) -> dict[str, Any]:
        """Return settings while preserving explicit null developer instructions."""

        data = self.model_dump(exclude_none=True)
        if "developer_instructions" in self.model_fields_set:
            data["developer_instructions"] = self.developer_instructions
        return data


class CodexAppServerOptions(YokeModel):
    """Codex app-server connection options."""

    ephemeral: bool | None = None
    policy: RequestPolicy | dict[str, Any] | None = None
    request_handler: Any | None = Field(
        default=None,
        exclude=True,
        json_schema_extra={
            "runtime_only": True,
            "reason": (
                "Callbacks are live Python objects. Configure request_handler "
                "in SDK code, not in a Yoke folder."
            ),
        },
    )
    opt_out_notification_methods: tuple[str, ...] = Field(
        default=(),
        validation_alias=AliasChoices(
            "opt_out_notification_methods",
            "optOutNotificationMethods",
        ),
    )
    mcp_server_openai_form_elicitation: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "mcp_server_openai_form_elicitation",
            "mcpServerOpenaiFormElicitation",
        ),
    )

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    def exposure(self, *, experimental_api: bool = False) -> CodexAppServerExposure:
        """Return stable, experimental, and runtime-only app-server fields."""

        stable: list[str] = []
        if self.opt_out_notification_methods:
            stable.append("initialize.capabilities.optOutNotificationMethods")
        if self.mcp_server_openai_form_elicitation:
            stable.append("initialize.capabilities.mcpServerOpenaiFormElicitation")
        experimental = (
            ("initialize.capabilities.experimentalApi",)
            if experimental_api
            else ()
        )
        return CodexAppServerExposure(
            stable=tuple(stable),
            experimental=experimental,
            runtime=self.runtime_options(),
        )

    def capabilities(self, *, experimental_api: bool = False) -> dict[str, Any]:
        """Return initialize.params.capabilities fields."""

        capabilities: dict[str, Any] = {}
        if experimental_api:
            capabilities["experimentalApi"] = True
        if self.opt_out_notification_methods:
            capabilities["optOutNotificationMethods"] = list(
                self.opt_out_notification_methods
            )
        if self.mcp_server_openai_form_elicitation:
            capabilities["mcpServerOpenaiFormElicitation"] = True
        return capabilities


class ProviderOptions(YokeModel):
    """Provider-specific options.

    Common options are typed; `raw` fields keep space for provider features Yoke
    has not modeled yet.
    """

    claude: ClaudeOptions | dict[str, Any] = Field(default_factory=ClaudeOptions)
    codex: CodexOptions | dict[str, Any] = Field(default_factory=CodexOptions)

    def runtime_options(self) -> tuple[RuntimeOption, ...]:
        """Return active SDK-only fields that will not round-trip through folders."""

        return runtime_options(self)

    def features(self, *, provider: object | None = None) -> tuple[Feature, ...]:
        """Return provider features implied by provider-specific options."""

        features: list[Feature] = []
        if provider in (None, "claude"):
            extend_unique(features, provider_option_features(self.claude, "claude"))
        if provider in (None, "codex"):
            extend_unique(features, provider_option_features(self.codex, "codex"))
        return tuple(features)


def provider_option_features(options: object, provider: str) -> tuple[Feature, ...]:
    """Return features for typed or raw provider option values."""

    from yoke.capabilities import Feature

    if isinstance(options, (ClaudeOptions, CodexOptions)):
        return options.features()
    if not isinstance(options, dict):
        return ()
    if provider == "claude":
        features: list[Feature] = []
        if options.get("permission_mode") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("permissionMode") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("allowed_tools") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("allowedTools") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("disallowed_tools") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("disallowedTools") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        if options.get("can_use_tool") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
            features.append(Feature.REQUEST_CALLBACKS)
        if options.get("canUseTool") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
            features.append(Feature.REQUEST_CALLBACKS)
        if options.get("request_handler") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
            features.append(Feature.REQUEST_CALLBACKS)
        if options.get("requestHandler") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
            features.append(Feature.REQUEST_CALLBACKS)
        if options.get("policy") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
            features.append(Feature.REQUEST_CALLBACKS)
        if options.get("hooks") is not None:
            features.append(Feature.CLAUDE_PERMISSIONS)
        raw = options.get("raw")
        if isinstance(raw, dict):
            extend_unique(features, provider_option_features(raw, provider))
        deduped: list[Feature] = []
        extend_unique(deduped, tuple(features))
        return tuple(deduped)
    if provider != "codex":
        return ()
    features: list[Feature] = []
    if options.get("experimental_api") is True:
        features.append(Feature.EXPERIMENTAL_API)
    if options.get("experimentalApi") is True:
        features.append(Feature.EXPERIMENTAL_API)
    if options.get("collaboration") is not None:
        features.append(Feature.COLLABORATION_MODE)
    if options.get("collaboration_mode") is not None:
        features.append(Feature.COLLABORATION_MODE)
    if options.get("collaborationMode") is not None:
        features.append(Feature.COLLABORATION_MODE)
    app_server = options.get("app_server", options.get("appServer"))
    if codex_app_server_requests_present(app_server):
        features.append(Feature.REQUEST_EVENTS)
    if codex_permission_options_present(options):
        features.append(Feature.CODEX_PERMISSIONS)
    raw = options.get("raw")
    if isinstance(raw, dict):
        extend_unique(features, provider_option_features(raw, provider))
    deduped: list[Feature] = []
    extend_unique(deduped, tuple(features))
    return tuple(deduped)


def codex_permission_options_present(options: dict[str, Any]) -> bool:
    """Return whether a raw Codex option dict contains native permission controls."""

    return any(
        options.get(key) is not None
        for key in (
            "sandbox",
            "approval",
            "approval_policy",
            "approvalPolicy",
            "approvals_reviewer",
            "approvalsReviewer",
            "network",
            "network_access",
            "networkAccess",
            "writable_roots",
            "writableRoots",
        )
    )


def codex_app_server_options(value: object) -> CodexAppServerOptions:
    """Return typed app-server options from typed, raw, or missing input."""

    if isinstance(value, CodexAppServerOptions):
        return value
    if isinstance(value, dict):
        return CodexAppServerOptions.model_validate(value)
    return CodexAppServerOptions()


def codex_app_server_requests_present(value: object) -> bool:
    """Return whether app-server request handling is configured."""

    if isinstance(value, CodexAppServerOptions):
        return value.request_handler is not None or value.policy is not None
    if isinstance(value, dict):
        return (
            value.get("request_handler") is not None
            or value.get("requestHandler") is not None
            or value.get("policy") is not None
        )
    return False


def extend_unique(items: list[Feature], values: tuple[Feature, ...]) -> None:
    """Append values that are not already present."""

    for value in values:
        if value not in items:
            items.append(value)
