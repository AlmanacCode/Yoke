"""Combined local status for a provider surface."""

from __future__ import annotations

from enum import StrEnum

from yoke.capabilities import Feature, Support, SurfaceReport
from yoke.models import Readiness, YokeModel


class GoalMode(StrEnum):
    """How a provider surface receives Yoke goals."""

    NATIVE_THREAD = "native_thread"
    PROVIDER_LOOP = "provider_loop"
    COMPILED_CONTEXT = "compiled_context"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class WorkflowMode(StrEnum):
    """How a provider surface runs workflows."""

    PROVIDER_NATIVE = "provider_native"
    YOKE_PORTABLE = "yoke_portable"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SubagentMode(StrEnum):
    """How a provider surface exposes delegated agents."""

    PROVIDER_NATIVE = "provider_native"
    DECLARED = "declared"
    COMPILED = "compiled"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SkillMode(StrEnum):
    """How a provider surface exposes skills."""

    PROVIDER_NATIVE = "provider_native"
    COMPILED = "compiled"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ControlMode(StrEnum):
    """How Yoke can control or inspect a provider surface."""

    PROGRAMMATIC = "programmatic"
    EXTERNAL_AUTH = "external_auth"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class PermissionMode(StrEnum):
    """How a provider surface exposes permission controls."""

    CODEX_NATIVE = "codex_native"
    CLAUDE_NATIVE = "claude_native"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class ExposureMode(StrEnum):
    """How callers configure and integrate with a provider surface."""

    CLI = "cli"
    SDK = "sdk"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


class GoalReport(YokeModel):
    """Goal behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    mode: GoalMode
    run: Support
    loop: Support
    mutable: Support
    readable: Support
    auto_continues: bool = False
    note: str | None = None


class WorkflowReport(YokeModel):
    """Workflow behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    mode: WorkflowMode
    portable: Support
    native: Support
    background: bool = False
    script: bool = False
    resumable: bool = False
    max_concurrent_agents: int | None = None
    max_agents: int | None = None
    note: str | None = None


class SubagentReport(YokeModel):
    """Subagent behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    mode: SubagentMode
    inline: Support
    declared: Support
    filesystem: Support
    collab: Support
    definition_sources: tuple[str, ...] = ()
    built_in: bool = False
    agent_tool: bool = False
    events: bool = False
    note: str | None = None


class SkillReport(YokeModel):
    """Skill and extension behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    mode: SkillMode
    skills: Support
    plugins: Support
    hooks: Support
    mcp: Support
    note: str | None = None


class ControlReport(YokeModel):
    """Runtime control and authentication behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    mode: ControlMode
    login: Support
    models: Support
    interrupt: Support
    fork: Support
    request_events: Support
    request_callbacks: Support
    experimental: Support
    note: str | None = None


class PermissionReport(YokeModel):
    """Permission control behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    mode: PermissionMode
    neutral: bool = False
    sandbox: bool = False
    approval: bool = False
    network: bool = False
    approval_reviewer: bool = False
    permission_mode: bool = False
    tool_rules: bool = False
    hooks: bool = False
    callbacks: bool = False
    dynamic: bool = False
    note: str | None = None


class HistoryReport(YokeModel):
    """Stored session/thread history behavior for one provider surface."""

    provider: str
    surface: str
    channel: str
    list: Support
    read: Support
    resume: Support
    compact: Support
    rename: Support
    tag: Support
    note: str | None = None


class ExposureReport(YokeModel):
    """Configuration and integration shape for one provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    mode: ExposureMode
    protocol: str | None = None
    stable: bool = False
    experimental: Support = Support.UNSUPPORTED
    runtime_options: bool = False
    note: str | None = None


class Status(YokeModel):
    """Local readiness plus declared capability metadata."""

    readiness: Readiness
    report: SurfaceReport

    @property
    def available(self) -> bool:
        """Whether the selected surface is locally ready."""

        return self.readiness.available

    @property
    def message(self) -> str:
        """Return the local readiness message."""

        return self.readiness.message

    @property
    def fix(self) -> str | None:
        """Return the suggested local readiness fix, if any."""

        return self.readiness.fix

    @property
    def provider(self) -> str:
        """Return the provider family."""

        return self.report.provider

    @property
    def surface(self) -> str:
        """Return the exact provider surface."""

        return self.report.surface

    @property
    def channel(self) -> str:
        """Return the broad provider exposure channel."""

        return self.report.channel

    def support_for(self, feature: Feature | str) -> Support:
        """Return support for one feature in this status report."""

        feature_value = str(Feature(feature))
        for row in self.report.features:
            if row.feature == feature_value:
                return Support(row.support)
        return Support.UNSUPPORTED

    def supports(self, feature: Feature | str) -> bool:
        """Return whether this status report says the surface supports a feature."""

        return self.support_for(feature) not in (
            Support.UNSUPPORTED,
            Support.UNKNOWN,
        )

    @property
    def exposure(self) -> ExposureReport:
        """Return how callers configure and integrate with this surface."""

        experimental = self.support_for(Feature.EXPERIMENTAL_API)
        if self.channel == "app_server":
            return ExposureReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=ExposureMode.PROTOCOL,
                protocol=f"{self.provider}_app_server_json_rpc",
                stable=True,
                experimental=experimental,
                runtime_options=True,
                note=(
                    "This surface is a JSON-RPC app integration surface. "
                    "Stable initialize and turn fields can be durable config; "
                    "experimental fields require explicit capability opt-in; "
                    "client callbacks remain runtime-only SDK code."
                ),
            )
        if self.channel == "sdk":
            return ExposureReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=ExposureMode.SDK,
                protocol=f"{self.provider}_sdk",
                stable=True,
                experimental=experimental,
                runtime_options=True,
                note=(
                    "This surface is an SDK object graph. Serializable options "
                    "can live in Yoke folders, but callbacks and live clients "
                    "belong in SDK code."
                ),
            )
        if self.channel == "cli":
            return ExposureReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=ExposureMode.CLI,
                protocol="process",
                stable=True,
                experimental=experimental,
                runtime_options=False,
                note=(
                    "This surface is configured through process arguments, "
                    "provider config files, and compiled provider artifacts."
                ),
            )
        return ExposureReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            runtime=self.report.runtime,
            mode=ExposureMode.UNKNOWN,
            experimental=experimental,
            note="Yoke has no exposure metadata for this custom provider surface.",
        )

    @property
    def goal(self) -> GoalReport:
        """Return goal semantics for the selected provider surface."""

        run = self.support_for(Feature.GOAL)
        loop = self.support_for(Feature.GOAL_LOOP)
        mutable = self.support_for(Feature.MUTABLE_GOAL)
        readable = self.support_for(Feature.READABLE_GOAL)

        if mutable is Support.NATIVE or readable is Support.NATIVE:
            mode = GoalMode.NATIVE_THREAD
            note = (
                "Goals are native provider thread state; use session goal "
                "methods when you need read or update control."
            )
            if loop is Support.NATIVE:
                note = (
                    f"{note} This surface also documents provider-owned goal "
                    "continuation beyond one normal run."
                )
        elif loop is Support.NATIVE:
            mode = GoalMode.PROVIDER_LOOP
            note = (
                "The provider surface documents a provider-owned goal loop, "
                "usually through slash-command behavior, but Yoke does not "
                "expose readable or mutable goal state through this surface."
            )
        elif run in (Support.NATIVE, Support.COMPILED, Support.EMULATED):
            mode = GoalMode.COMPILED_CONTEXT
            note = (
                "Goals are passed as run or session context; Yoke does not "
                "turn them into an automatic keep-working loop."
            )
        elif run is Support.UNKNOWN:
            mode = GoalMode.UNKNOWN
            note = "Yoke has no goal metadata for this custom provider surface."
        else:
            mode = GoalMode.UNSUPPORTED
            note = "This provider surface does not support Yoke goals."

        return GoalReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            mode=mode,
            run=run,
            loop=loop,
            mutable=mutable,
            readable=readable,
            auto_continues=loop is Support.NATIVE,
            note=note,
        )

    @property
    def workflow(self) -> WorkflowReport:
        """Return workflow semantics for the selected provider surface."""

        portable = self.support_for(Feature.WORKFLOW)
        native = self.support_for(Feature.NATIVE_WORKFLOW)

        if native is Support.NATIVE:
            mode = WorkflowMode.PROVIDER_NATIVE
            note = (
                "The provider surface exposes a native workflow primitive. "
                "Use it for provider-script/background orchestration."
            )
        elif portable in (Support.NATIVE, Support.COMPILED, Support.EMULATED):
            mode = WorkflowMode.YOKE_PORTABLE
            note = (
                "Yoke runs workflows as portable step orchestration over "
                "provider turns."
            )
        elif portable is Support.UNKNOWN or native is Support.UNKNOWN:
            mode = WorkflowMode.UNKNOWN
            note = "Yoke has no workflow metadata for this provider surface."
        else:
            mode = WorkflowMode.UNSUPPORTED
            note = "This provider surface does not support Yoke workflows."

        return WorkflowReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            mode=mode,
            portable=portable,
            native=native,
            background=native is Support.NATIVE,
            script=native is Support.NATIVE,
            resumable=native is Support.NATIVE,
            max_concurrent_agents=16 if native is Support.NATIVE else None,
            max_agents=1000 if native is Support.NATIVE else None,
            note=note,
        )

    @property
    def subagents(self) -> SubagentReport:
        """Return subagent semantics for the selected provider surface."""

        inline = self.support_for(Feature.INLINE_SUBAGENTS)
        declared = self.support_for(Feature.DECLARED_SUBAGENTS)
        filesystem = self.support_for(Feature.FILESYSTEM_AGENT)
        collab = self.support_for(Feature.COLLAB_AGENT_TOOLS)

        if collab is Support.NATIVE:
            mode = SubagentMode.PROVIDER_NATIVE
            note = (
                "The provider surface exposes native spawned-agent activity. "
                "Yoke-declared subagents remain separate definitions or prompt "
                "context unless the surface maps them directly."
            )
        elif inline is Support.NATIVE or declared is Support.NATIVE:
            mode = SubagentMode.DECLARED
            note = (
                "Yoke subagents map to provider-recognized agent definitions."
            )
        elif inline in (Support.COMPILED, Support.EMULATED) or declared in (
            Support.COMPILED,
            Support.EMULATED,
        ):
            mode = SubagentMode.COMPILED
            note = (
                "Yoke subagents are compiled into instructions or provider "
                "artifacts; the provider does not expose them as live spawned "
                "agent activity on this surface."
            )
        elif (
            inline is Support.UNKNOWN
            or declared is Support.UNKNOWN
            or filesystem is Support.UNKNOWN
            or collab is Support.UNKNOWN
        ):
            mode = SubagentMode.UNKNOWN
            note = "Yoke has incomplete subagent metadata for this provider surface."
        else:
            mode = SubagentMode.UNSUPPORTED
            note = "This provider surface does not support Yoke subagents."

        return SubagentReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            runtime=self.report.runtime,
            mode=mode,
            inline=inline,
            declared=declared,
            filesystem=filesystem,
            collab=collab,
            definition_sources=subagent_definition_sources(
                self.provider,
                inline,
                declared,
                filesystem,
            ),
            built_in=self.provider == "claude"
            and declared in (Support.NATIVE, Support.UNKNOWN),
            agent_tool=self.provider == "claude"
            and (
                inline is Support.NATIVE
                or declared is Support.NATIVE
                or filesystem is Support.NATIVE
            ),
            events=collab is Support.NATIVE
            or (
                self.provider == "claude"
                and (
                    inline is Support.NATIVE
                    or declared is Support.NATIVE
                    or filesystem is Support.NATIVE
                )
            ),
            note=note,
        )

    @property
    def skills(self) -> SkillReport:
        """Return skill and extension semantics for the selected provider surface."""

        skills = self.support_for(Feature.SKILLS)
        plugins = self.support_for(Feature.PLUGINS)
        hooks = self.support_for(Feature.HOOKS)
        mcp = self.support_for(Feature.MCP)

        if skills is Support.NATIVE:
            mode = SkillMode.PROVIDER_NATIVE
            note = (
                "The provider surface can discover or load filesystem skills. "
                "Yoke can preserve skill bundles instead of flattening them "
                "into prompt text."
            )
        elif skills in (Support.COMPILED, Support.EMULATED):
            mode = SkillMode.COMPILED
            note = (
                "Yoke compiles skills into instructions for this surface; "
                "supporting files are not provider-native skill bundles."
            )
        elif skills is Support.UNKNOWN:
            mode = SkillMode.UNKNOWN
            note = "Yoke has incomplete skill metadata for this provider surface."
        else:
            mode = SkillMode.UNSUPPORTED
            note = "This provider surface does not support Yoke skills."

        return SkillReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            runtime=self.report.runtime,
            mode=mode,
            skills=skills,
            plugins=plugins,
            hooks=hooks,
            mcp=mcp,
            note=note,
        )

    @property
    def control(self) -> ControlReport:
        """Return runtime control and authentication support for this surface."""

        login = self.support_for(Feature.LOGIN)
        models = self.support_for(Feature.MODELS)
        interrupt = self.support_for(Feature.INTERRUPT)
        fork = self.support_for(Feature.FORK)
        request_events = self.support_for(Feature.REQUEST_EVENTS)
        request_callbacks = self.support_for(Feature.REQUEST_CALLBACKS)
        experimental = self.support_for(Feature.EXPERIMENTAL_API)
        live_controls = (
            models,
            interrupt,
            fork,
            request_events,
            request_callbacks,
            experimental,
        )

        if login is Support.NATIVE:
            mode = ControlMode.PROGRAMMATIC
            note = (
                "Yoke can start this surface's login flow and inspect or use "
                "the reported runtime controls through the selected adapter."
            )
        elif any(control is Support.NATIVE for control in live_controls):
            mode = ControlMode.EXTERNAL_AUTH
            note = (
                "This surface exposes runtime controls, but authentication is "
                "handled outside Yoke through the provider's normal setup."
            )
        elif login is Support.UNKNOWN or any(
            control is Support.UNKNOWN for control in live_controls
        ):
            mode = ControlMode.UNKNOWN
            note = "Yoke has incomplete control metadata for this provider surface."
        else:
            mode = ControlMode.UNSUPPORTED
            note = (
                "This surface does not expose login, model, interrupt, fork, "
                "or experimental API controls to Yoke."
            )

        return ControlReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            runtime=self.report.runtime,
            mode=mode,
            login=login,
            models=models,
            interrupt=interrupt,
            fork=fork,
            request_events=request_events,
            request_callbacks=request_callbacks,
            experimental=experimental,
            note=note,
        )

    @property
    def permissions(self) -> PermissionReport:
        """Return provider permission-control support for this surface."""

        if self.provider == "codex":
            return PermissionReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=PermissionMode.CODEX_NATIVE,
                neutral=True,
                sandbox=True,
                approval=True,
                network=True,
                approval_reviewer=True,
                note=(
                    "Codex separates sandbox boundaries, approval policy, "
                    "network access, and optional approval review."
                ),
            )
        if self.provider == "claude" and self.channel == "sdk":
            return PermissionReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=PermissionMode.CLAUDE_NATIVE,
                neutral=True,
                permission_mode=True,
                tool_rules=True,
                hooks=True,
                callbacks=True,
                dynamic=True,
                note=(
                    "Claude Agent SDK evaluates hooks, deny/ask rules, "
                    "permission mode, allow rules, and runtime callbacks."
                ),
            )
        if self.provider == "claude" and self.surface == "claude_cli":
            return PermissionReport(
                provider=self.provider,
                surface=self.surface,
                channel=self.channel,
                runtime=self.report.runtime,
                mode=PermissionMode.EXTERNAL,
                neutral=True,
                note=(
                    "This Claude surface is configured through provider tools "
                    "outside Yoke's SDK adapter."
                ),
            )
        return PermissionReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            runtime=self.report.runtime,
            mode=PermissionMode.UNKNOWN,
            note="Yoke has no permission metadata for this custom provider surface.",
        )

    @property
    def history(self) -> HistoryReport:
        """Return stored session/thread history support for this surface."""

        listing = self.support_for(Feature.SESSION_LIST)
        read = self.support_for(Feature.SESSION_READ)
        resume = self.support_for(Feature.SESSION_RESUME)
        compact = self.support_for(Feature.SESSION_COMPACT)
        rename = self.support_for(Feature.SESSION_RENAME)
        tag = self.support_for(Feature.SESSION_TAG)
        if listing is Support.NATIVE or read is Support.NATIVE:
            note = "This surface can inspect stored provider sessions/threads."
        elif compact is Support.NATIVE:
            note = (
                "This surface can compact live provider sessions, but does not "
                "expose stored session history to Yoke."
            )
        elif listing is Support.UNKNOWN or read is Support.UNKNOWN:
            note = "Yoke has no stored-history metadata for this provider surface."
        else:
            note = "This surface does not expose stored session history to Yoke."
        return HistoryReport(
            provider=self.provider,
            surface=self.surface,
            channel=self.channel,
            list=listing,
            read=read,
            resume=resume,
            compact=compact,
            rename=rename,
            tag=tag,
            note=note,
        )


def subagent_definition_sources(
    provider: str,
    inline: Support,
    declared: Support,
    filesystem: Support,
) -> tuple[str, ...]:
    """Return the human-visible definition channels for subagents."""

    sources: list[str] = []
    if inline is Support.NATIVE or declared is Support.NATIVE:
        if provider == "claude":
            sources.append("agents_parameter")
        else:
            sources.append("provider_definitions")
    if filesystem is Support.NATIVE:
        if provider == "claude":
            sources.append(".claude/agents")
        elif provider == "codex":
            sources.append(".codex/agents")
        else:
            sources.append("filesystem")
    if declared in (Support.COMPILED, Support.EMULATED):
        sources.append("compiled_instructions")
    return tuple(dict.fromkeys(sources))
