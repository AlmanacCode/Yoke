"""Surface capability matrix."""

from __future__ import annotations

from collections.abc import Iterable

from yoke.capabilities import (
    Capabilities,
    Feature,
    FeatureReport,
    Fit,
    Profile,
    ProviderReport,
    Support,
    SurfaceReport,
)
from yoke.errors import UnsupportedFeature
from yoke.models import (
    Channel,
    Provider,
    Surface,
    normalize_provider_surface,
    split_provider_surface,
)


def capabilities_for(
    provider: Provider | str,
    surface: Surface | str | None = None,
) -> Capabilities:
    """Return Yoke's current capability matrix for a provider surface."""

    return profile_for(provider, surface).capabilities


def report_for(
    provider: Provider | str,
    surface: Surface | str | None = None,
) -> SurfaceReport:
    """Return a JSON-friendly capability report for one provider surface."""

    profile = profile_for(provider, surface)
    surface_key = f"{profile.provider}:{profile.surface}"
    return SurfaceReport(
        key=surface_key,
        provider=str(profile.provider),
        surface=str(profile.surface),
        channel=str(profile.channel),
        runtime=profile.runtime,
        default=profile.default,
        runnable=profile.runnable,
        evidence=surface_evidence(profile.provider, str(profile.surface)),
        features=tuple(
            FeatureReport(
                feature=str(feature),
                support=str(capability.support),
                note=capability.note,
                lowering=feature_lowering(
                    profile.provider,
                    str(profile.surface),
                    feature,
                ),
                recipes=feature_recipes(
                    profile.provider,
                    str(profile.surface),
                    feature,
                ),
                evidence=feature_evidence(
                    profile.provider,
                    str(profile.surface),
                    feature,
                ),
            )
            for feature, capability in sorted(
                profile.capabilities.features.items(),
                key=lambda item: str(item[0]),
            )
        ),
    )


def reports_for(
    provider: Provider | str,
    *,
    channel: Channel | str | None = None,
    runnable: bool | None = None,
) -> tuple[SurfaceReport, ...]:
    """Return JSON-friendly capability reports for known provider surfaces."""

    return tuple(
        report_for(profile.provider, profile.surface)
        for profile in profiles_for(provider, channel=channel, runnable=runnable)
    )


def matrix_for(
    provider: Provider | str,
    *,
    channel: Channel | str | None = None,
    runnable: bool | None = None,
) -> ProviderReport:
    """Return one JSON-friendly provider capability matrix."""

    provider_part, embedded_surface = split_provider_surface(provider)
    provider_value = Provider(provider_part)
    channel_value = Channel(channel) if channel is not None else None
    if embedded_surface is not None:
        report = report_for(provider_value, embedded_surface)
        if channel_value is not None and report.channel != str(channel_value):
            return ProviderReport(
                provider=str(provider_value),
                channel=str(channel_value),
                runnable=runnable,
                surfaces=(),
            )
        if runnable is not None and report.runnable is not runnable:
            return ProviderReport(
                provider=str(provider_value),
                channel=str(channel_value) if channel_value is not None else None,
                runnable=runnable,
                surfaces=(),
            )
        return ProviderReport(
            provider=str(provider_value),
            channel=str(channel_value) if channel_value is not None else None,
            runnable=runnable,
            surfaces=(report,),
        )
    return ProviderReport(
        provider=str(provider_value),
        channel=str(channel_value) if channel_value is not None else None,
        runnable=runnable,
        surfaces=reports_for(
            provider_value,
            channel=channel_value,
            runnable=runnable,
        ),
    )


def profiles_for(
    provider: Provider | str,
    *,
    channel: Channel | str | None = None,
    runnable: bool | None = None,
) -> tuple[Profile, ...]:
    """Return all known Yoke profiles for a provider."""

    provider_part, embedded_surface = split_provider_surface(provider)
    provider_value = Provider(provider_part)
    channel_value = Channel(channel) if channel is not None else None
    if embedded_surface is not None:
        profile = profile_for(provider_value, embedded_surface)
        if channel_value is not None and profile.channel != channel_value:
            return ()
        if runnable is not None and profile.runnable is not runnable:
            return ()
        return (profile,)
    profiles = tuple(
        profile_for(provider_value, surface)
        for matrix_provider, surface in MATRIX
        if matrix_provider is provider_value
    )
    if channel_value is not None:
        profiles = tuple(
            profile for profile in profiles if profile.channel == channel_value
        )
    if runnable is None:
        return profiles
    return tuple(profile for profile in profiles if profile.runnable is runnable)


def select_profile(
    provider: Provider | str,
    *,
    requires: Iterable[Feature | str] = (),
    channel: Channel | str | None = None,
    runnable: bool | None = None,
) -> Profile:
    """Choose the best known surface for a provider and feature set."""

    required = tuple(Feature(feature) for feature in requires)
    channel_value = Channel(channel) if channel is not None else None
    if not required:
        profiles = profiles_for(provider, channel=channel_value, runnable=runnable)
        if profiles:
            return profiles[0]
        channel_text = f" {channel_value}" if channel_value else ""
        runnable_text = " runnable" if runnable else ""
        raise UnsupportedFeature(
            f"no known{runnable_text}{channel_text} {provider} surface"
        )
    fits = fits_for(
        provider,
        requires=required,
        channel=channel_value,
        runnable=runnable,
    )
    candidates = [fit for fit in fits if fit.ok]
    if not candidates:
        feature_names = ", ".join(str(feature) for feature in required)
        channel_text = f" {channel_value}" if channel_value else ""
        runnable_text = " runnable" if runnable else ""
        considered = "; ".join(describe_fit(fit) for fit in fits)
        considered_text = f" Considered: {considered}." if considered else ""
        raise UnsupportedFeature(
            f"no known{runnable_text}{channel_text} {provider} surface "
            "supports required "
            f"features: {feature_names}.{considered_text}"
        )
    return max(
        candidates,
        key=lambda fit: (fit.required_score, fit.total_score),
    ).profile


def fits_for(
    provider: Provider | str,
    *,
    requires: Iterable[Feature | str] = (),
    channel: Channel | str | None = None,
    runnable: bool | None = None,
) -> tuple[Fit, ...]:
    """Rank known profiles by fit for a feature set."""

    required = tuple(Feature(feature) for feature in requires)
    fits = tuple(
        fit_profile(profile, required)
        for profile in profiles_for(provider, channel=channel, runnable=runnable)
    )
    return tuple(
        sorted(
            fits,
            key=lambda fit: (fit.ok, fit.required_score, fit.total_score),
            reverse=True,
        )
    )


def fit_profile(profile: Profile, required: tuple[Feature, ...]) -> Fit:
    """Score one profile against required features."""

    required_score, total_score = score_profile(profile, required)
    return Fit(
        profile=profile,
        requires=required,
        missing=profile.missing(required),
        required_score=required_score,
        total_score=total_score,
    )


def describe_fit(fit: Fit) -> str:
    """Return a compact diagnostic summary for one fit."""

    if fit.ok:
        return f"{fit.profile.surface} supports all required features"
    missing = ", ".join(str(feature) for feature in fit.missing)
    return f"{fit.profile.surface} missing {missing}"


def score_profile(profile: Profile, required: tuple[Feature, ...]) -> tuple[int, int]:
    """Score a profile for selection."""

    required_score = sum(
        SUPPORT_RANK[profile.support_for(feature)] for feature in required
    )
    total_score = sum(
        SUPPORT_RANK[capability.support]
        for capability in profile.capabilities.features.values()
    )
    return required_score, total_score


def profile_for(
    provider: Provider | str,
    surface: Surface | str | None = None,
) -> Profile:
    """Return the resolved provider surface profile."""

    provider_part, surface_part = split_provider_surface(provider, surface)
    provider_value = Provider(provider_part)
    is_default = surface_part is None
    surface_value = normalize_provider_surface(provider_value, surface_part)
    surface_value = surface_value or default_surface(provider_value)
    key = (provider_value, str(surface_value))
    from yoke.adapters import has_adapter, registered_capabilities

    registered = registered_capabilities(provider_value, str(surface_value))
    if registered is not None:
        capabilities = registered
    else:
        try:
            capabilities = MATRIX[key]
        except KeyError:
            capabilities = unknown_surface(provider_value, str(surface_value))

    return Profile(
        provider=provider_value,
        surface=surface_value,
        channel=channel_for(provider_value, str(surface_value)),
        runtime=runtime_for(provider_value, str(surface_value)),
        capabilities=capabilities,
        default=is_default,
        runnable=has_adapter(provider_value, str(surface_value)),
    )


def channel_for(provider: Provider | str, surface: Surface | str) -> Channel:
    """Return the broad exposure path for a provider surface."""

    try:
        provider_value = Provider(provider)
    except ValueError:
        return Channel.CUSTOM
    return SURFACE_CHANNELS.get((provider_value, str(surface)), Channel.CUSTOM)


def runtime_for(provider: Provider | str, surface: Surface | str) -> str:
    """Return the provider runtime that backs a surface."""

    try:
        provider_value = Provider(provider)
    except ValueError:
        return "custom"
    return SURFACE_RUNTIMES.get((provider_value, str(surface)), "custom")


def surface_evidence(provider: Provider, surface: str) -> tuple[str, ...]:
    """Return source material that anchors a known surface report."""

    return SURFACE_EVIDENCE.get((provider, surface), ())


def feature_evidence(
    provider: Provider,
    surface: str,
    feature: Feature,
) -> tuple[str, ...]:
    """Return source material that anchors one feature claim."""

    return FEATURE_EVIDENCE.get(
        (provider, surface, feature),
        surface_evidence(provider, surface),
    )


def feature_lowering(
    provider: Provider,
    surface: str,
    feature: Feature,
) -> str | None:
    """Return how Yoke lowers a feature on one provider surface."""

    return FEATURE_LOWERING.get((provider, surface, feature))


def feature_recipes(
    provider: Provider,
    surface: str,
    feature: Feature,
) -> tuple[str, ...]:
    """Return Yoke entrypoints for one feature on one provider surface."""

    return FEATURE_RECIPES.get((provider, surface, feature), ())


def default_surface(provider: Provider) -> Surface:
    if provider is Provider.CLAUDE:
        return Surface.CLAUDE_PYTHON_SDK
    if provider is Provider.OPENCODE:
        return Surface.OPENCODE_SERVER
    return Surface.CODEX_APP_SERVER


def unknown_surface(provider: Provider, surface: str) -> Capabilities:
    return Capabilities.from_map(
        {
            feature: (
                Support.UNKNOWN,
                f"Yoke has no capability declaration for {provider}:{surface}.",
            )
            for feature in Feature
        }
    )


SUPPORT_RANK: dict[Support, int] = {
    Support.NATIVE: 4,
    Support.COMPILED: 3,
    Support.EMULATED: 2,
    Support.UNKNOWN: 0,
    Support.UNSUPPORTED: 0,
}


SURFACE_CHANNELS: dict[tuple[Provider, str], Channel] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK): Channel.SDK,
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK): Channel.SDK,
    (Provider.CLAUDE, Surface.CLAUDE_CLI): Channel.CLI,
    (Provider.CODEX, Surface.CODEX_CLI): Channel.CLI,
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK): Channel.SDK,
    (Provider.CODEX, Surface.CODEX_TYPESCRIPT_SDK): Channel.SDK,
    (Provider.CODEX, Surface.CODEX_APP_SERVER): Channel.APP_SERVER,
    (Provider.OPENCODE, Surface.OPENCODE_SERVER): Channel.APP_SERVER,
}


SURFACE_RUNTIMES: dict[tuple[Provider, str], str] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK): "claude_code",
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK): "claude_code",
    (Provider.CLAUDE, Surface.CLAUDE_CLI): "claude_code",
    (Provider.CODEX, Surface.CODEX_CLI): "codex_exec",
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK): "codex_app_server",
    (Provider.CODEX, Surface.CODEX_TYPESCRIPT_SDK): "codex_sdk",
    (Provider.CODEX, Surface.CODEX_APP_SERVER): "codex_app_server",
    (Provider.OPENCODE, Surface.OPENCODE_SERVER): "opencode_server",
}


SURFACE_EVIDENCE: dict[tuple[Provider, str], tuple[str, ...]] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK): (
        "https://code.claude.com/docs/en/agent-sdk/python",
        "https://code.claude.com/docs/en/sub-agents",
        "https://code.claude.com/docs/en/skills",
        "https://code.claude.com/docs/en/hooks",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK): (
        "https://code.claude.com/docs/en/agent-sdk/typescript",
        "https://code.claude.com/docs/en/sub-agents",
        "https://code.claude.com/docs/en/skills",
        "https://code.claude.com/docs/en/hooks",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_CLI): (
        "https://code.claude.com/docs/en/cli-reference",
        "https://code.claude.com/docs/en/sub-agents",
        "https://code.claude.com/docs/en/skills",
        "https://code.claude.com/docs/en/hooks",
    ),
    (Provider.CODEX, Surface.CODEX_CLI): (
        "https://developers.openai.com/codex/cli/reference",
        "https://developers.openai.com/codex/llms-full.txt",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK): (
        "https://developers.openai.com/codex/sdk",
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_TYPESCRIPT_SDK): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER): (
        "https://developers.openai.com/codex/app-server",
        "https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER): (
        "https://opencode.ai/docs/server/",
        "https://opencode.ai/docs/skills/",
        "https://opencode.ai/docs/mcp-servers/",
        "https://opencode.ai/docs/config/",
        "https://opencode.ai/docs/providers/",
    ),
}


FEATURE_EVIDENCE: dict[tuple[Provider, str, Feature], tuple[str, ...]] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.INLINE_SUBAGENTS): (
        "https://code.claude.com/docs/en/agent-sdk/subagents",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.DECLARED_SUBAGENTS): (
        "https://code.claude.com/docs/en/agent-sdk/subagents",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SKILLS): (
        "https://code.claude.com/docs/en/agent-sdk/skills",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.PLUGINS): (
        "https://code.claude.com/docs/en/agent-sdk/plugins",
        "https://code.claude.com/docs/en/plugins",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_LIST): (
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_READ): (
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RESUME): (
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_COMPACT): (
        "https://code.claude.com/docs/en/agent-sdk/file-checkpointing",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RENAME): (
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_TAG): (
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.HOOKS): (
        "https://code.claude.com/docs/en/agent-sdk/hooks",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.REQUEST_CALLBACKS): (
        "https://code.claude.com/docs/en/agent-sdk/user-input",
        "https://code.claude.com/docs/en/agent-sdk/permissions",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.GOAL_LOOP): (
        "https://code.claude.com/docs/en/goal",
        "https://code.claude.com/docs/en/agent-sdk/python",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.REQUEST_CALLBACKS): (
        "https://code.claude.com/docs/en/agent-sdk/user-input",
        "https://code.claude.com/docs/en/agent-sdk/permissions",
        "https://code.claude.com/docs/en/agent-sdk/typescript",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.NATIVE_WORKFLOW): (
        "https://code.claude.com/docs/en/agent-sdk/subagents",
        "https://code.claude.com/docs/en/agent-sdk/typescript",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.WORKFLOW): (
        "https://code.claude.com/docs/en/agent-sdk/subagents",
        "https://code.claude.com/docs/en/agent-sdk/typescript",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_CLI, Feature.GOAL_LOOP): (
        "https://code.claude.com/docs/en/goal",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.FILESYSTEM_AGENT): (
        "https://developers.openai.com/codex/subagents",
        "https://developers.openai.com/codex/cli/reference",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.GOAL_LOOP): (
        "https://developers.openai.com/codex/use-cases/follow-goals",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.SKILLS): (
        "https://developers.openai.com/codex/cli/reference",
        "https://developers.openai.com/codex/llms-full.txt",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.PLUGINS): (
        "https://developers.openai.com/codex/changelog",
        "https://developers.openai.com/codex/skills",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.STREAMING): (
        "https://developers.openai.com/codex/cli/reference",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.ONE_SHOT): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.SESSION): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.STREAMING): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.LOGIN): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.FORK): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.INTERRUPT): (
        "https://developers.openai.com/codex/sdk",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.STREAMING): (
        "https://developers.openai.com/codex/app-server",
        "https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_LIST): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_READ): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RESUME): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_COMPACT): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RENAME): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.MODELS): (
        "https://developers.openai.com/codex/app-server",
        "https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.COLLAB_AGENT_TOOLS): (
        "https://developers.openai.com/codex/subagents",
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.COLLABORATION_MODE): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL): (
        "https://developers.openai.com/codex/app-server",
        "https://developers.openai.com/codex/use-cases/follow-goals",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL_LOOP): (
        "https://developers.openai.com/codex/use-cases/follow-goals",
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.MUTABLE_GOAL): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.READABLE_GOAL): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.INTERRUPT): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.FORK): (
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.EXPERIMENTAL_API): (
        "https://developers.openai.com/codex/app-server",
        "https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.PLUGINS): (
        "https://developers.openai.com/codex/changelog",
        "https://developers.openai.com/codex/app-server",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.REQUEST_EVENTS): (
        "https://developers.openai.com/codex/app-server",
        "https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_LIST): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_READ): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_RENAME): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_COMPACT): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.FORK): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.INTERRUPT): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.MODELS): (
        "https://opencode.ai/docs/server/",
        "https://opencode.ai/docs/providers/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.LOGIN): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SKILLS): (
        "https://opencode.ai/docs/skills/",
        "https://opencode.ai/docs/config/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.INLINE_SUBAGENTS): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.STREAMING): (
        "https://opencode.ai/docs/server/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.MCP): (
        "https://opencode.ai/docs/mcp-servers/",
        "https://opencode.ai/docs/config/",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.PERMISSIONS): (
        "https://opencode.ai/docs/server/",
    ),
}


FEATURE_LOWERING: dict[tuple[Provider, str, Feature], str] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.INLINE_SUBAGENTS): (
        "Yoke subagents become Claude SDK AgentDefinition values in query options."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.DECLARED_SUBAGENTS): (
        "Yoke subagents can be supplied programmatically or written as "
        ".claude/agents/*.md artifacts."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SKILLS): (
        "Yoke inline skills can be written as .claude/skills/<name>/SKILL.md; "
        "path-backed skills remain filesystem skills."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.PLUGINS): (
        "Yoke folder roots with skills/ are passed as Claude local plugins; "
        "plugin packaging is the native loading mechanism for folder skills."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.REQUEST_CALLBACKS): (
        "ClaudeOptions(can_use_tool=...) is passed to ClaudeAgentOptions; "
        "tool approvals and AskUserQuestion prompts pause inside that callback."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.REQUEST_CALLBACKS): (
        "Claude TypeScript SDK exposes the same canUseTool callback shape; "
        "Yoke tracks the feature but does not run a TypeScript adapter yet."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.WORKFLOW): (
        "Yoke executes workflow steps as SDK turns; this is not Claude's "
        "TypeScript Workflow tool."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.GOAL_LOOP): (
        "Yoke sends /goal <objective> through the Claude Agent SDK "
        "slash-command path. Claude owns the Stop-hook evaluator and "
        "continuation loop."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_LIST): (
        "Harness.sessions() calls Claude SDK list_sessions()."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_READ): (
        "Harness.read_session() calls Claude SDK get_session_info() and "
        "get_session_messages()."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RESUME): (
        "Harness.start(SessionOptions(resume=...)) passes resume into "
        "ClaudeAgentOptions."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_COMPACT): (
        "Claude file checkpointing can rewind filesystem changes, but Yoke "
        "does not lower it to conversation compaction."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RENAME): (
        "Harness.rename_session() and Session.rename() call Claude SDK "
        "rename_session()."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_TAG): (
        "Harness.tag_session() and Session.tag() call Claude SDK tag_session()."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.NATIVE_WORKFLOW): (
        "Claude TypeScript SDK exposes the native Workflow tool; Yoke tracks "
        "the surface but does not run it from the Python adapter."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.FILESYSTEM_AGENT): (
        "Yoke subagents write .codex/agents/*.toml custom-agent files."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.DECLARED_SUBAGENTS): (
        "Direct CLI runs compile declared Yoke subagents into prompt text; "
        "bundle() writes native .codex/agents files."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.SKILLS): (
        "Yoke inline skills can be written as .agents/skills/<name>/SKILL.md; "
        "direct runs also compile inline skills into instructions."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.PLUGINS): (
        "Codex plugins package skills, MCP, app integrations, and config. "
        "Yoke currently bundles skills and agents as provider files rather than "
        "installing Codex plugins."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.WORKFLOW): (
        "Yoke executes workflow steps as multiple CLI turns."
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.DECLARED_SUBAGENTS): (
        "Yoke subagents compile into SDK developer instructions for this surface."
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.WORKFLOW): (
        "Yoke executes workflow steps as multiple SDK thread turns."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.DECLARED_SUBAGENTS): (
        "Yoke compiles declared subagents into guidance for native Codex "
        "spawn_agent calls, including requested model overrides, and normalizes "
        "collab events when the parent delegates."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.COLLAB_AGENT_TOOLS): (
        "Codex app-server emits native collabToolCall events, with legacy "
        "collabAgentToolCall events also accepted, for actions such as "
        "spawnAgent; Yoke normalizes them into AgentCall event payloads."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SKILLS): (
        "Yoke wires skill roots into the app-server environment and can bundle "
        "inline skills as filesystem skill artifacts."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.PLUGINS): (
        "Codex app-server can import external agent configuration including "
        "plugins; Yoke currently exposes skill roots and provider artifacts."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.REQUEST_EVENTS): (
        "Codex app-server server requests become approval_request, "
        "user_input_request, or tool_request events; "
        "CodexAppServerOptions(request_handler=...) can answer them."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL): (
        "Run goals can compile into instructions; session goal methods use "
        "app-server thread/goal JSON-RPC."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL_LOOP): (
        "Codex documents Goals as persisted thread state with provider-owned "
        "continuation policy; app-server exposes the same persisted goal state "
        "as /goal."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.MUTABLE_GOAL): (
        "Session.set_goal and clear_goal call app-server thread/goal methods."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.READABLE_GOAL): (
        "Session.get_goal calls app-server thread/goal/get."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.WORKFLOW): (
        "Yoke executes workflow steps as app-server turns; native collab agents "
        "are observed through events, not used as the workflow runtime."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_LIST): (
        "Harness.sessions() calls app-server thread/list."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_READ): (
        "Harness.read_session() calls app-server thread/read."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RESUME): (
        "Harness.start(SessionOptions(resume=...)) calls app-server thread/resume."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_COMPACT): (
        "Session.compact() calls app-server thread/compact/start."
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RENAME): (
        "Harness.rename_session() and Session.rename() call app-server "
        "thread/name/set."
    ),
    (Provider.CLAUDE, Surface.CLAUDE_CLI, Feature.GOAL_LOOP): (
        "Claude Code /goal starts a turn and runs an evaluator after each turn; "
        "Yoke tracks it as provider-native but does not run Claude CLI yet."
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.GOAL_LOOP): (
        "Codex /goal is provider-native interactive behavior; Yoke's codex_cli "
        "adapter remains a bounded codex exec wrapper."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_LIST): (
        "Harness.sessions() calls GET /session."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_READ): (
        "Harness.read_session() calls GET /session/:id, plus a read-only poll "
        "of OpenCode's own message table for message history."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_RENAME): (
        "Harness.rename_session() and Session.rename() call PATCH /session/:id."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_COMPACT): (
        "Session.compact() calls POST /session/:id/summarize."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.FORK): (
        "Session.fork() calls POST /session/:id/fork."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.INTERRUPT): (
        "Session.interrupt() calls POST /session/:id/abort."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.MODELS): (
        "GET /config/providers lists provider/model pairs OpenCode can route to."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.LOGIN): (
        "harness.login('api_key', api_key=...) calls PUT /auth/:id. OAuth "
        "authorize/callback exists in the API but is not wired in this "
        "adapter yet."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SKILLS): (
        "Yoke skills render as SKILL.md files under a Yoke-owned deployment "
        "directory; OPENCODE_CONFIG_DIR points OpenCode at it without "
        "touching the user's real project."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.INLINE_SUBAGENTS): (
        "OpenCode's built-in `task` tool spawns a child session; Yoke "
        "normalizes the spawn/settle lifecycle into AgentCall event payloads."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.STREAMING): (
        "Yoke polls OpenCode's own SQLite part/message tables while a turn is "
        "in flight and emits events as new terminal parts appear; OpenCode's "
        "SSE stream was found unreliable for this in a prior live spike."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.MCP): (
        "MCP servers compile into OPENCODE_CONFIG_CONTENT/OPENCODE_CONFIG_DIR "
        "config, since OpenCode has no runtime add-server endpoint."
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.PERMISSIONS): (
        "Session creation always passes an allow-all permission block; there "
        "is no polling-discoverable pending-permission signal to build a "
        "live approval loop on without depending on SSE."
    ),
}


FEATURE_RECIPES: dict[tuple[Provider, str, Feature], tuple[str, ...]] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.ONE_SHOT): (
        'await Harness(provider="claude", surface="sdk").run(prompt)',
        'Harness(provider="claude", surface="sdk").run_sync(prompt)',
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION): (
        'session = await Harness(provider="claude", surface="sdk").start()',
        "await session.run(prompt)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.STREAMING): (
        "async for event in harness.stream(prompt): ...",
        "async for event in session.stream(prompt): ...",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_LIST): (
        "sessions = await harness.sessions(limit=10)",
        "sessions = harness.sessions_sync(limit=10)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_READ): (
        "history = await harness.read_session(session_id)",
        "history = harness.read_session_sync(session_id)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RESUME): (
        "session = await harness.start(SessionOptions(resume=session_id))",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_RENAME): (
        "renamed = await harness.rename_session(session_id, title)",
        "renamed = await session.rename(title)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SESSION_TAG): (
        "tagged = await harness.tag_session(session_id, tag)",
        "tagged = await session.tag(tag)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.INLINE_SUBAGENTS): (
        "Agent(subagents=[Agent(name=..., instructions=...)])",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.DECLARED_SUBAGENTS): (
        "agent.bundle(provider='claude', surface='sdk')",
        "save(agent, path)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.SKILLS): (
        "Agent(skills=[Skill(name=..., instructions=...)])",
        "save(agent, path)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.PLUGINS): (
        'agent = Agent.from_folder("agent")',
        'await Harness("claude:sdk", agent=agent, cwd=repo).run(prompt)',
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.REQUEST_CALLBACKS): (
        "ClaudeOptions(can_use_tool=handler)",
        "RunOptions(provider=ProviderOptions(claude=ClaudeOptions(...)))",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.GOAL): (
        'Agent(goal=Goal("..."))',
        'RunOptions(goal=Goal("..."))',
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.GOAL_LOOP): (
        'await Harness("claude", agent=agent).goal_loop(GoalLoopOptions(goal=goal))',
    ),
    (Provider.CLAUDE, Surface.CLAUDE_CLI, Feature.GOAL_LOOP): (
        'claude -p "/goal <condition>"',
        "/goal <condition>",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.INTERRUPT): (
        "await session.interrupt()",
        "session.interrupt_sync()",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.FORK): (
        "fork = await session.fork()",
        "fork = session.fork_sync()",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK, Feature.WORKFLOW): (
        "await harness.workflow(workflow, prompt)",
        "harness.workflow_sync(workflow, prompt)",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.NATIVE_WORKFLOW): (
        "Tracked as provider-native; no built-in Yoke Python adapter yet.",
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK, Feature.REQUEST_CALLBACKS): (
        "Tracked as provider-native; no built-in Yoke Python adapter yet.",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.ONE_SHOT): (
        'await Harness(provider="codex", surface="cli").run(prompt)',
        'Harness(provider="codex", surface="cli").run_sync(prompt)',
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.SESSION): (
        'session = await Harness(provider="codex", surface="cli").start()',
        "await session.run(prompt)",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.STREAMING): (
        "async for event in harness.stream(prompt): ...",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.DECLARED_SUBAGENTS): (
        "agent.bundle(provider='codex', surface='cli')",
        "save(agent, path)",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.SKILLS): (
        "Agent(skills=[Skill(name=..., instructions=...)])",
        "save(agent, path)",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.PLUGINS): (
        "install Codex plugin through Codex app/CLI",
        "agent.bundle(provider='codex').write(repo)",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.GOAL): (
        'RunOptions(goal=Goal("..."))',
        'Agent(goal=Goal("..."))',
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.GOAL_LOOP): (
        "/goal <objective>",
        "/goal pause",
        "/goal resume",
        "/goal clear",
    ),
    (Provider.CODEX, Surface.CODEX_CLI, Feature.WORKFLOW): (
        "await harness.workflow(workflow, prompt)",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.ONE_SHOT): (
        'await Harness(provider="codex", surface="sdk").run(prompt)',
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.SESSION): (
        'session = await Harness(provider="codex", surface="sdk").start()',
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.STREAMING): (
        "async for event in session.stream(prompt): ...",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.LOGIN): (
        'await harness.login("chatgpt")',
        'await harness.login("device_code")',
        'await harness.login("api_key", api_key=...)',
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.INTERRUPT): (
        "await session.interrupt()",
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK, Feature.FORK): (
        "fork = await session.fork()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.ONE_SHOT): (
        'await Harness(provider="codex", surface="app").run(prompt)',
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION): (
        'session = await Harness(provider="codex", surface="app").start()',
        "await session.run(prompt)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_LIST): (
        "sessions = await harness.sessions(limit=25)",
        "sessions = await harness.sessions(cursor=page.next_cursor)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_READ): (
        "history = await harness.read_session(thread_id)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RESUME): (
        "session = await harness.start(SessionOptions(resume=thread_id))",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_COMPACT): (
        "await session.compact()",
        "session.compact_sync()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SESSION_RENAME): (
        "renamed = await harness.rename_session(thread_id, title)",
        "renamed = await session.rename(title)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.STREAMING): (
        "async for event in harness.stream(prompt): ...",
        "async for event in session.stream(prompt): ...",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.REQUEST_EVENTS): (
        "CodexAppServerOptions(request_handler=handler)",
        "event.kind in {'approval_request', 'user_input_request', 'tool_request'}",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.MODELS): (
        "models = await harness.models()",
        "models = harness.models_sync()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.COLLAB_AGENT_TOOLS): (
        "async for event in session.stream(prompt): ...",
        "event.agent_call",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.COLLABORATION_MODE): (
        "RunOptions(provider=ProviderOptions(codex=CodexOptions(...)))",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.SKILLS): (
        "Agent(skills=[Skill(name=..., instructions=...)])",
        "save(agent, path)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.PLUGINS): (
        "use app-server externalAgentConfig/import for Codex plugins",
        "use Yoke bundles for provider files",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL): (
        'RunOptions(goal=Goal("..."))',
        'SessionOptions(goal=Goal("..."))',
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.GOAL_LOOP): (
        "await session.set_goal(goal)",
        "continue only when the thread is idle and the goal remains active",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.MUTABLE_GOAL): (
        "await session.set_goal(goal)",
        "await session.clear_goal()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.READABLE_GOAL): (
        "goal = await session.get_goal()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.INTERRUPT): (
        "await session.interrupt()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.FORK): (
        "fork = await session.fork()",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.WORKFLOW): (
        "await harness.workflow(workflow, prompt)",
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER, Feature.EXPERIMENTAL_API): (
        "CodexAppServerOptions(experimental_api=True)",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.ONE_SHOT): (
        'await Harness(provider="opencode", agent=agent, cwd=repo).run(prompt)',
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION): (
        'session = await Harness(provider="opencode", agent=agent, cwd=repo).start()',
        "await session.run(prompt)",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_LIST): (
        "sessions = await harness.sessions()",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_READ): (
        "history = await harness.read_session(session_id)",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_COMPACT): (
        "await session.compact()",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SESSION_RENAME): (
        "renamed = await harness.rename_session(session_id, title)",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.STREAMING): (
        "RunOptions(on_event=callback)",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.MODELS): (
        "models = await harness.models()",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.LOGIN): (
        'await harness.login("api_key", api_key=...)',
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.INTERRUPT): (
        "await session.interrupt()",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.FORK): (
        "fork = await session.fork()",
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER, Feature.SKILLS): (
        "Agent(skills=[Skill(name=..., instructions=...)])",
    ),
}


MATRIX: dict[tuple[Provider, str], Capabilities] = {
    (Provider.CLAUDE, Surface.CLAUDE_PYTHON_SDK): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: (
                Support.NATIVE,
                "Claude Python SDK exposes list_sessions().",
            ),
            Feature.SESSION_READ: (
                Support.NATIVE,
                "Claude Python SDK exposes get_session_info() and "
                "get_session_messages().",
            ),
            Feature.SESSION_RESUME: (
                Support.NATIVE,
                "ClaudeAgentOptions supports resume for persisted sessions.",
            ),
            Feature.SESSION_COMPACT: (
                Support.UNSUPPORTED,
                "Claude file checkpointing rewinds filesystem state; it is not "
                "conversation compaction.",
            ),
            Feature.SESSION_RENAME: (
                Support.NATIVE,
                "Claude Python SDK exposes rename_session().",
            ),
            Feature.SESSION_TAG: (
                Support.NATIVE,
                "Claude Python SDK exposes tag_session().",
            ),
            Feature.STREAMING: Support.NATIVE,
            Feature.RUN_EVENT_CALLBACKS: (
                Support.NATIVE,
                "Claude Python SDK one-shot runs deliver normalized events "
                "to a synchronous callback.",
            ),
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.MODELS: Support.UNSUPPORTED,
            Feature.LOGIN: (
                Support.UNSUPPORTED,
                "Claude SDK authentication is external to Yoke.",
            ),
            Feature.PERMISSIONS: Support.NATIVE,
            Feature.REQUEST_CALLBACKS: (
                Support.NATIVE,
                "Claude SDK canUseTool handles tool approvals and "
                "AskUserQuestion prompts through a live callback.",
            ),
            Feature.CODEX_PERMISSIONS: Support.UNSUPPORTED,
            Feature.CLAUDE_PERMISSIONS: (
                Support.NATIVE,
                "Claude Python SDK accepts permission_mode and tool allow/deny "
                "rules through ClaudeAgentOptions.",
            ),
            Feature.FILESYSTEM_AGENT: (
                Support.NATIVE,
                "Claude SDK can load filesystem agents; programmatic agents with "
                "the same name take precedence.",
            ),
            Feature.INLINE_SUBAGENTS: (
                Support.NATIVE,
                "Yoke subagents map to Claude SDK AgentDefinition values.",
            ),
            Feature.DECLARED_SUBAGENTS: (
                Support.NATIVE,
                "Yoke subagents map to Claude SDK AgentDefinition values.",
            ),
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: (
                Support.NATIVE,
                "Yoke folder skills load as local Claude plugins; inline skills "
                "still compile into prompt text.",
            ),
            Feature.PLUGINS: (
                Support.NATIVE,
                "Claude Python SDK loads local plugin roots; Yoke uses this for "
                "folder skills.",
            ),
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: (
                Support.COMPILED,
                "Claude receives Yoke goals through prompt and task_budget.",
            ),
            Feature.GOAL_LOOP: (
                Support.NATIVE,
                "Yoke sends Claude Code /goal through the Python SDK prompt "
                "path. Claude owns the slash-command loop, but the SDK does "
                "not expose readable or mutable goal state.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: (
                Support.NATIVE,
                "ClaudeSDKClient exposes interrupt() for live streaming sessions.",
            ),
            Feature.FORK: (
                Support.NATIVE,
                "Yoke forks Claude Python SDK sessions by starting a new "
                "ClaudeSDKClient with resume=<provider_session_id> and "
                "fork_session=True. Partial forks are not wired.",
            ),
            Feature.WORKFLOW: (
                Support.EMULATED,
                "Yoke executes workflows over Claude turns. Claude dynamic "
                "Workflow is TypeScript-SDK-native, not Python-wired in Yoke yet.",
            ),
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: Support.UNSUPPORTED,
        }
    ),
    (Provider.CLAUDE, Surface.CLAUDE_TYPESCRIPT_SDK): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: Support.NATIVE,
            Feature.SESSION_READ: Support.NATIVE,
            Feature.SESSION_RESUME: Support.NATIVE,
            Feature.SESSION_COMPACT: Support.UNSUPPORTED,
            Feature.SESSION_RENAME: Support.UNKNOWN,
            Feature.SESSION_TAG: Support.UNKNOWN,
            Feature.STREAMING: Support.NATIVE,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.MODELS: Support.UNSUPPORTED,
            Feature.LOGIN: (
                Support.UNSUPPORTED,
                "Claude TypeScript SDK authentication is external to Yoke.",
            ),
            Feature.PERMISSIONS: Support.NATIVE,
            Feature.REQUEST_CALLBACKS: (
                Support.NATIVE,
                "Claude TypeScript SDK canUseTool handles tool approvals and "
                "AskUserQuestion prompts through a live callback.",
            ),
            Feature.CODEX_PERMISSIONS: Support.UNSUPPORTED,
            Feature.CLAUDE_PERMISSIONS: Support.NATIVE,
            Feature.FILESYSTEM_AGENT: Support.NATIVE,
            Feature.INLINE_SUBAGENTS: Support.NATIVE,
            Feature.DECLARED_SUBAGENTS: Support.NATIVE,
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: Support.NATIVE,
            Feature.PLUGINS: Support.NATIVE,
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: Support.COMPILED,
            Feature.GOAL_LOOP: (
                Support.UNSUPPORTED,
                "Claude TypeScript Agent SDK workflows are distinct from the "
                "Claude Code /goal loop.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: Support.UNKNOWN,
            Feature.FORK: Support.UNKNOWN,
            Feature.WORKFLOW: (
                Support.NATIVE,
                "Claude documents the Workflow tool on the TypeScript Agent SDK.",
            ),
            Feature.NATIVE_WORKFLOW: (
                Support.NATIVE,
                "Claude documents the Workflow tool on the TypeScript Agent SDK.",
            ),
            Feature.EXPERIMENTAL_API: Support.UNSUPPORTED,
        }
    ),
    (Provider.CLAUDE, Surface.CLAUDE_CLI): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.UNKNOWN,
            Feature.SESSION: Support.UNKNOWN,
            Feature.SESSION_LIST: Support.UNKNOWN,
            Feature.SESSION_READ: Support.UNKNOWN,
            Feature.SESSION_RESUME: Support.NATIVE,
            Feature.SESSION_COMPACT: Support.UNKNOWN,
            Feature.SESSION_RENAME: Support.UNKNOWN,
            Feature.SESSION_TAG: Support.UNKNOWN,
            Feature.STREAMING: Support.UNKNOWN,
            Feature.STRUCTURED_OUTPUT: Support.UNKNOWN,
            Feature.MODELS: Support.UNSUPPORTED,
            Feature.LOGIN: (
                Support.UNSUPPORTED,
                "Claude CLI authentication is an external interactive flow.",
            ),
            Feature.PERMISSIONS: Support.UNKNOWN,
            Feature.CODEX_PERMISSIONS: Support.UNSUPPORTED,
            Feature.CLAUDE_PERMISSIONS: Support.UNKNOWN,
            Feature.FILESYSTEM_AGENT: Support.NATIVE,
            Feature.INLINE_SUBAGENTS: Support.UNSUPPORTED,
            Feature.DECLARED_SUBAGENTS: Support.NATIVE,
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: Support.NATIVE,
            Feature.PLUGINS: Support.NATIVE,
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: Support.COMPILED,
            Feature.GOAL_LOOP: (
                Support.NATIVE,
                "Claude Code /goal keeps the session running across turns until "
                "a small-model evaluator says the condition is met.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: Support.UNKNOWN,
            Feature.FORK: (
                Support.NATIVE,
                "Claude CLI exposes --fork-session when resuming or continuing "
                "a session.",
            ),
            Feature.WORKFLOW: Support.UNKNOWN,
            Feature.NATIVE_WORKFLOW: Support.UNKNOWN,
            Feature.EXPERIMENTAL_API: Support.UNSUPPORTED,
        }
    ),
    (Provider.CODEX, Surface.CODEX_CLI): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: (
                Support.COMPILED,
                "codex_cli sessions are resumable exec threads, not live processes.",
            ),
            Feature.SESSION_LIST: Support.UNSUPPORTED,
            Feature.SESSION_READ: Support.UNSUPPORTED,
            Feature.SESSION_RESUME: (
                Support.COMPILED,
                "Yoke resumes Codex CLI sessions through codex exec resume.",
            ),
            Feature.SESSION_COMPACT: (
                Support.UNSUPPORTED,
                "codex_cli sessions are bounded exec runs; Yoke has no live "
                "thread compaction handle.",
            ),
            Feature.SESSION_RENAME: Support.UNSUPPORTED,
            Feature.SESSION_TAG: Support.UNSUPPORTED,
            Feature.STREAMING: (
                Support.NATIVE,
                "codex exec emits JSONL events for each turn.",
            ),
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.MODELS: Support.UNSUPPORTED,
            Feature.LOGIN: (
                Support.UNSUPPORTED,
                "Codex CLI login is external; run `codex login`.",
            ),
            Feature.PERMISSIONS: Support.NATIVE,
            Feature.CODEX_PERMISSIONS: (
                Support.UNSUPPORTED,
                "Yoke's CodexOptions sandbox/approval fields are wired for "
                "app-server turns, not direct codex exec runs.",
            ),
            Feature.CLAUDE_PERMISSIONS: Support.UNSUPPORTED,
            Feature.FILESYSTEM_AGENT: (
                Support.NATIVE,
                "Codex discovers custom agents from .codex/agents/*.toml.",
            ),
            Feature.INLINE_SUBAGENTS: Support.UNSUPPORTED,
            Feature.DECLARED_SUBAGENTS: (
                Support.COMPILED,
                "Yoke-declared subagents compile into prompt instructions during "
                "direct CLI runs; bundle() can write native .codex agent files.",
            ),
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: (
                Support.NATIVE,
                "Codex CLI supports agent skills; Yoke direct CLI runs still "
                "compile inline skills into prompt text.",
            ),
            Feature.PLUGINS: (
                Support.NATIVE,
                "Codex plugins are available in the app, CLI, and IDE surfaces; "
                "Yoke does not install them directly yet.",
            ),
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: (
                Support.COMPILED,
                "CLI runs receive goals in the prompt; app-server owns native "
                "mutable goals.",
            ),
            Feature.GOAL_LOOP: (
                Support.NATIVE,
                "Codex documents /goal as a native interactive CLI goal loop; "
                "Yoke's direct codex_cli adapter still uses bounded codex exec "
                "runs.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: (
                Support.UNSUPPORTED,
                "codex_cli sessions are resumed exec processes; Yoke has no live "
                "turn handle to interrupt.",
            ),
            Feature.FORK: (
                Support.UNSUPPORTED,
                "codex_cli does not expose a native session fork operation.",
            ),
            Feature.WORKFLOW: (
                Support.EMULATED,
                "Yoke executes workflows by making multiple CLI turns.",
            ),
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: Support.UNSUPPORTED,
        }
    ),
    (Provider.CODEX, Surface.CODEX_PYTHON_SDK): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: Support.UNKNOWN,
            Feature.SESSION_READ: Support.UNKNOWN,
            Feature.SESSION_RESUME: Support.NATIVE,
            Feature.SESSION_COMPACT: Support.UNKNOWN,
            Feature.SESSION_RENAME: Support.UNKNOWN,
            Feature.SESSION_TAG: Support.UNKNOWN,
            Feature.STREAMING: Support.NATIVE,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.MODELS: Support.NATIVE,
            Feature.LOGIN: (
                Support.NATIVE,
                "Codex Python SDK exposes ChatGPT, device-code, and API-key login.",
            ),
            Feature.PERMISSIONS: Support.NATIVE,
            Feature.CODEX_PERMISSIONS: (
                Support.UNSUPPORTED,
                "Yoke's CodexOptions sandbox/approval fields are wired through "
                "the app-server adapter, not the public Python SDK adapter.",
            ),
            Feature.CLAUDE_PERMISSIONS: Support.UNSUPPORTED,
            Feature.FILESYSTEM_AGENT: Support.UNKNOWN,
            Feature.INLINE_SUBAGENTS: Support.UNSUPPORTED,
            Feature.DECLARED_SUBAGENTS: (
                Support.COMPILED,
                "Yoke-declared subagents compile into SDK developer instructions.",
            ),
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: (
                Support.COMPILED,
                "Yoke inline skills compile into developer instructions; SDK "
                "SkillInput support is not wired yet.",
            ),
            Feature.PLUGINS: (
                Support.UNSUPPORTED,
                "Codex Python SDK does not expose Codex app/CLI plugin install "
                "or import as a Yoke adapter operation.",
            ),
            Feature.HOOKS: Support.UNSUPPORTED,
            Feature.MCP: (
                Support.COMPILED,
                "The SDK can pass Codex config, but Yoke has not typed MCP setup "
                "for this surface yet.",
            ),
            Feature.GOAL: (
                Support.COMPILED,
                "The public Python SDK run/thread API does not expose native "
                "thread goal methods.",
            ),
            Feature.GOAL_LOOP: (
                Support.UNSUPPORTED,
                "Codex Python SDK runs are bounded by the caller; native /goal "
                "continuation is not exposed as a Python SDK method.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: (
                Support.NATIVE,
                "Codex Python SDK turn handles expose interrupt(); Yoke wires "
                "this for active streamed turns.",
            ),
            Feature.FORK: (
                Support.NATIVE,
                "Codex Python SDK exposes thread_fork; Yoke keeps forked "
                "sessions on the same live SDK client with shared ownership.",
            ),
            Feature.WORKFLOW: (
                Support.EMULATED,
                "Yoke executes workflows by making multiple SDK turns.",
            ),
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: (
                Support.UNSUPPORTED,
                "The public Python SDK wraps app-server but Yoke has not exposed "
                "app-server experimental API controls through this surface.",
            ),
        }
    ),
    (Provider.CODEX, Surface.CODEX_TYPESCRIPT_SDK): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: Support.UNKNOWN,
            Feature.SESSION_READ: Support.UNKNOWN,
            Feature.SESSION_RESUME: Support.UNKNOWN,
            Feature.SESSION_COMPACT: Support.UNKNOWN,
            Feature.SESSION_RENAME: Support.UNKNOWN,
            Feature.SESSION_TAG: Support.UNKNOWN,
            Feature.STREAMING: Support.UNKNOWN,
            Feature.STRUCTURED_OUTPUT: Support.UNKNOWN,
            Feature.MODELS: Support.UNKNOWN,
            Feature.LOGIN: Support.UNKNOWN,
            Feature.PERMISSIONS: Support.UNKNOWN,
            Feature.CODEX_PERMISSIONS: Support.UNKNOWN,
            Feature.CLAUDE_PERMISSIONS: Support.UNSUPPORTED,
            Feature.FILESYSTEM_AGENT: Support.UNKNOWN,
            Feature.INLINE_SUBAGENTS: Support.UNSUPPORTED,
            Feature.DECLARED_SUBAGENTS: Support.COMPILED,
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNKNOWN,
            Feature.SKILLS: Support.UNKNOWN,
            Feature.PLUGINS: Support.UNKNOWN,
            Feature.HOOKS: Support.UNKNOWN,
            Feature.MCP: Support.UNKNOWN,
            Feature.GOAL: Support.COMPILED,
            Feature.GOAL_LOOP: Support.UNKNOWN,
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: Support.UNKNOWN,
            Feature.FORK: Support.UNKNOWN,
            Feature.WORKFLOW: Support.EMULATED,
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: Support.UNKNOWN,
        }
    ),
    (Provider.CODEX, Surface.CODEX_APP_SERVER): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: (
                Support.NATIVE,
                "Codex app-server exposes thread/list.",
            ),
            Feature.SESSION_READ: (
                Support.NATIVE,
                "Codex app-server exposes thread/read for stored threads.",
            ),
            Feature.SESSION_RESUME: (
                Support.NATIVE,
                "Codex app-server exposes thread/resume.",
            ),
            Feature.SESSION_COMPACT: (
                Support.NATIVE,
                "Codex app-server exposes thread/compact/start.",
            ),
            Feature.SESSION_RENAME: (
                Support.NATIVE,
                "Codex app-server exposes thread/name/set.",
            ),
            Feature.SESSION_TAG: (
                Support.UNSUPPORTED,
                "Codex app-server does not expose a portable session tag API.",
            ),
            Feature.STREAMING: (
                Support.NATIVE,
                "Yoke yields app-server notifications as they arrive.",
            ),
            Feature.RUN_EVENT_CALLBACKS: (
                Support.NATIVE,
                "Yoke delivers app-server one-shot run events to a synchronous "
                "callback as notifications arrive.",
            ),
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.MODELS: (
                Support.NATIVE,
                "Codex app-server exposes model/list for account-supported models.",
            ),
            Feature.LOGIN: (
                Support.UNSUPPORTED,
                "Codex app-server uses existing Codex authentication.",
            ),
            Feature.PERMISSIONS: Support.NATIVE,
            Feature.REQUEST_EVENTS: (
                Support.NATIVE,
                "Yoke normalizes app-server server requests as request events and "
                "answers them through CodexAppServerOptions.request_handler.",
            ),
            Feature.CODEX_PERMISSIONS: (
                Support.NATIVE,
                "Yoke lowers CodexOptions sandbox, approval, network, and "
                "writable_roots fields into app-server turn parameters.",
            ),
            Feature.CLAUDE_PERMISSIONS: Support.UNSUPPORTED,
            Feature.FILESYSTEM_AGENT: (
                Support.NATIVE,
                "Codex discovers custom agents from .codex/agents/*.toml.",
            ),
            Feature.INLINE_SUBAGENTS: (
                Support.UNSUPPORTED,
                "Use declared Yoke subagents so model and task semantics remain "
                "explicit across providers.",
            ),
            Feature.DECLARED_SUBAGENTS: (
                Support.COMPILED,
                "Yoke compiles declared subagents into native spawn_agent "
                "guidance; invocation remains model-driven.",
            ),
            Feature.COLLAB_AGENT_TOOLS: (
                Support.NATIVE,
                "Codex app-server emits collab agent tool calls such as spawnAgent.",
            ),
            Feature.COLLABORATION_MODE: (
                Support.NATIVE,
                "Codex app-server accepts collaborationMode turn parameters.",
            ),
            Feature.SKILLS: (
                Support.NATIVE,
                "Yoke wires packaged skills through app-server extra roots.",
            ),
            Feature.PLUGINS: (
                Support.NATIVE,
                "Codex app-server can import external agent configuration "
                "including plugins, but Yoke currently exposes skill roots and "
                "provider artifacts instead of plugin install management.",
            ),
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: Support.NATIVE,
            Feature.GOAL_LOOP: (
                Support.NATIVE,
                "Codex app-server exposes persisted goal state used by /goal; "
                "continuation belongs to the provider thread lifecycle.",
            ),
            Feature.MUTABLE_GOAL: Support.NATIVE,
            Feature.READABLE_GOAL: Support.NATIVE,
            Feature.INTERRUPT: (
                Support.NATIVE,
                "Codex app-server exposes turn/interrupt for active turns.",
            ),
            Feature.FORK: (
                Support.NATIVE,
                "Codex app-server exposes thread/fork for branching sessions.",
            ),
            Feature.WORKFLOW: (
                Support.EMULATED,
                "Yoke executes workflows over app-server turns.",
            ),
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: (
                Support.NATIVE,
                "Yoke initializes Codex app-server with capabilities.experimentalApi "
                "so experimental JSON-RPC methods and fields can be used.",
            ),
        }
    ),
    (Provider.OPENCODE, Surface.OPENCODE_SERVER): Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.SESSION_LIST: (Support.NATIVE, "GET /session."),
            Feature.SESSION_READ: (
                Support.NATIVE,
                "GET /session/:id plus a read-only poll of OpenCode's own "
                "message table.",
            ),
            Feature.SESSION_RESUME: (
                Support.UNKNOWN,
                "OpenCode sessions are addressed by id, but resuming a prior "
                "session into a fresh Harness.start() call is unconfirmed.",
            ),
            Feature.SESSION_COMPACT: (Support.NATIVE, "POST /session/:id/summarize."),
            Feature.SESSION_RENAME: (Support.NATIVE, "PATCH /session/:id."),
            Feature.SESSION_TAG: (
                Support.UNSUPPORTED,
                "No documented session tag concept.",
            ),
            Feature.STREAMING: (
                Support.EMULATED,
                "Poll-based, not OpenCode's native SSE stream, which a prior "
                "live spike found unreliable for this purpose.",
            ),
            Feature.RUN_EVENT_CALLBACKS: (
                Support.EMULATED,
                "RunOptions.on_event is driven by the DB-poll watchdog, not a "
                "native provider event stream.",
            ),
            Feature.STRUCTURED_OUTPUT: (
                Support.UNSUPPORTED,
                "No documented schema-constrained output API.",
            ),
            Feature.MODELS: (Support.NATIVE, "GET /config/providers."),
            Feature.LOGIN: (
                Support.NATIVE,
                "PUT /auth/:id sets api_key credentials; OAuth authorize/"
                "callback exists in the API but is not wired in this adapter.",
            ),
            Feature.PERMISSIONS: (
                Support.COMPILED,
                "Session creation always passes an allow-all permission block; "
                "no live per-request approval loop (see REQUEST_EVENTS).",
            ),
            Feature.REQUEST_CALLBACKS: (
                Support.UNSUPPORTED,
                "See REQUEST_EVENTS.",
            ),
            Feature.CODEX_PERMISSIONS: Support.UNSUPPORTED,
            Feature.CLAUDE_PERMISSIONS: Support.UNSUPPORTED,
            Feature.FILESYSTEM_AGENT: Support.UNSUPPORTED,
            Feature.INLINE_SUBAGENTS: (
                Support.NATIVE,
                "The built-in `task` tool spawns a child session, discovered "
                "and normalized by the DB-poll watchdog.",
            ),
            Feature.DECLARED_SUBAGENTS: (
                Support.UNKNOWN,
                "GET /agent lists agents but the on-disk format Yoke would "
                "need to write them in is unconfirmed.",
            ),
            Feature.COLLAB_AGENT_TOOLS: Support.UNSUPPORTED,
            Feature.COLLABORATION_MODE: Support.UNSUPPORTED,
            Feature.SKILLS: (
                Support.NATIVE,
                "OPENCODE_CONFIG_DIR points OpenCode at a Yoke-generated "
                "skills/<name>/SKILL.md directory without touching the "
                "user's real project.",
            ),
            Feature.PLUGINS: (
                Support.UNSUPPORTED,
                "OpenCode plugins are a separate JS extension mechanism, not "
                "modeled by Yoke.",
            ),
            Feature.HOOKS: Support.UNSUPPORTED,
            Feature.MCP: (
                Support.COMPILED,
                "MCP servers are config-file only; no runtime add-server API.",
            ),
            Feature.GOAL: Support.UNSUPPORTED,
            Feature.GOAL_LOOP: Support.UNSUPPORTED,
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.READABLE_GOAL: Support.UNSUPPORTED,
            Feature.INTERRUPT: (Support.NATIVE, "POST /session/:id/abort."),
            Feature.FORK: (Support.NATIVE, "POST /session/:id/fork."),
            Feature.WORKFLOW: (
                Support.EMULATED,
                "Yoke executes workflow steps as multiple session sends.",
            ),
            Feature.NATIVE_WORKFLOW: Support.UNSUPPORTED,
            Feature.EXPERIMENTAL_API: Support.UNSUPPORTED,
            Feature.REQUEST_EVENTS: (
                Support.UNSUPPORTED,
                "POST /session/:id/permissions/:permissionID can answer a "
                "pending request, but there is no polling-discoverable way to "
                "learn a permission is pending — OpenCode's docs indicate "
                "this is only learnable via SSE, which this adapter "
                "deliberately does not depend on.",
            ),
        }
    ),
}
