"""Provider capability language."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import Field

from yoke.errors import UnsupportedFeature
from yoke.models import Channel, Provider, Surface, YokeModel


class Feature(StrEnum):
    """Provider features Yoke knows how to reason about."""

    ONE_SHOT = "one_shot"
    SESSION = "session"
    SESSION_LIST = "session_list"
    SESSION_READ = "session_read"
    SESSION_RESUME = "session_resume"
    SESSION_COMPACT = "session_compact"
    SESSION_RENAME = "session_rename"
    SESSION_TAG = "session_tag"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured_output"
    MODELS = "models"
    LOGIN = "login"
    PERMISSIONS = "permissions"
    REQUEST_EVENTS = "request_events"
    REQUEST_CALLBACKS = "request_callbacks"
    CODEX_PERMISSIONS = "codex_permissions"
    CLAUDE_PERMISSIONS = "claude_permissions"
    FILESYSTEM_AGENT = "filesystem_agent"
    INLINE_SUBAGENTS = "inline_subagents"
    DECLARED_SUBAGENTS = "declared_subagents"
    COLLAB_AGENT_TOOLS = "collab_agent_tools"
    COLLABORATION_MODE = "collaboration_mode"
    SKILLS = "skills"
    PLUGINS = "plugins"
    HOOKS = "hooks"
    MCP = "mcp"
    GOAL = "goal"
    GOAL_LOOP = "goal_loop"
    MUTABLE_GOAL = "mutable_goal"
    READABLE_GOAL = "readable_goal"
    INTERRUPT = "interrupt"
    FORK = "fork"
    WORKFLOW = "workflow"
    NATIVE_WORKFLOW = "native_workflow"
    EXPERIMENTAL_API = "experimental_api"


class Support(StrEnum):
    """How directly a provider supports a feature."""

    NATIVE = "native"
    COMPILED = "compiled"
    EMULATED = "emulated"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class Capability(YokeModel):
    """One feature support entry."""

    feature: Feature
    support: Support
    note: str | None = None


class Coverage(YokeModel):
    """Support-count summary for a capability set."""

    total: int = 0
    native: int = 0
    compiled: int = 0
    emulated: int = 0
    unsupported: int = 0
    unknown: int = 0
    supported: int = 0
    percent_supported: float = 0.0

    @classmethod
    def from_supports(cls, supports: Iterable[Support | str]) -> Coverage:
        """Build a coverage summary from support values."""

        counts = {
            Support.NATIVE: 0,
            Support.COMPILED: 0,
            Support.EMULATED: 0,
            Support.UNSUPPORTED: 0,
            Support.UNKNOWN: 0,
        }
        total = 0
        for support in supports:
            support_value = Support(support)
            counts[support_value] += 1
            total += 1
        supported = (
            counts[Support.NATIVE]
            + counts[Support.COMPILED]
            + counts[Support.EMULATED]
        )
        percent_supported = round((supported / total) * 100, 1) if total else 0.0
        return cls(
            total=total,
            native=counts[Support.NATIVE],
            compiled=counts[Support.COMPILED],
            emulated=counts[Support.EMULATED],
            unsupported=counts[Support.UNSUPPORTED],
            unknown=counts[Support.UNKNOWN],
            supported=supported,
            percent_supported=percent_supported,
        )


class Capabilities(YokeModel):
    """Declared provider support matrix."""

    features: dict[Feature, Capability] = Field(default_factory=dict)

    def support_for(self, feature: Feature) -> Support:
        entry = self.features.get(feature)
        if entry is None:
            return Support.UNSUPPORTED
        return entry.support

    def supports(self, feature: Feature) -> bool:
        return self.support_for(feature) not in (Support.UNSUPPORTED, Support.UNKNOWN)

    def coverage(self) -> Coverage:
        """Return support-count coverage for this capability set."""

        return Coverage.from_supports(
            capability.support for capability in self.features.values()
        )

    @classmethod
    def from_map(
        cls,
        features: dict[Feature, Support | tuple[Support, str]],
    ) -> Capabilities:
        entries: dict[Feature, Capability] = {}
        for feature, value in features.items():
            if isinstance(value, tuple):
                support, note = value
            else:
                support, note = value, None
            entries[feature] = Capability(feature=feature, support=support, note=note)
        return cls(features=entries)


class Profile(YokeModel):
    """Resolved provider surface profile."""

    provider: Provider
    surface: Surface | str
    channel: Channel = Channel.CUSTOM
    runtime: str = "custom"
    capabilities: Capabilities
    default: bool = False
    runnable: bool = False

    def support_for(self, feature: Feature) -> Support:
        """Return support for one feature on this exact surface."""

        return self.capabilities.support_for(feature)

    def supports(self, feature: Feature) -> bool:
        """Return whether this exact surface supports a feature."""

        return self.capabilities.supports(feature)

    def supports_all(self, features: Iterable[Feature | str]) -> bool:
        """Return whether this exact surface supports every requested feature."""

        return all(self.supports(Feature(feature)) for feature in features)

    def missing(self, features: Iterable[Feature | str]) -> tuple[Feature, ...]:
        """Return requested features that this exact surface cannot satisfy."""

        return tuple(
            feature_value
            for feature in features
            if not self.supports(feature_value := Feature(feature))
        )


class Fit(YokeModel):
    """How well one profile satisfies a feature request."""

    profile: Profile
    requires: tuple[Feature, ...] = ()
    missing: tuple[Feature, ...] = ()
    required_score: int = 0
    total_score: int = 0

    @property
    def ok(self) -> bool:
        """Whether this profile satisfies every required feature."""

        return not self.missing


class Plan(YokeModel):
    """Resolved surface plan for a feature request."""

    features: tuple[Feature, ...] = ()
    channel: Channel | None = None
    channel_mismatch: bool = False
    fit: Fit
    candidates: tuple[Fit, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether the selected fit satisfies the feature request."""

        return self.fit.ok and not self.channel_mismatch

    @property
    def profile(self) -> Profile:
        """Return the selected profile."""

        return self.fit.profile

    @property
    def provider(self) -> Provider:
        """Return the selected provider."""

        return self.profile.provider

    @property
    def surface(self) -> Surface | str:
        """Return the selected surface."""

        return self.profile.surface

    @property
    def missing(self) -> tuple[Feature, ...]:
        """Return required features the selected surface cannot satisfy."""

        return self.fit.missing

    @property
    def reports(self) -> tuple[FeatureReport, ...]:
        """Return selected-surface support rows for requested features."""

        from yoke.surfaces import (
            feature_evidence,
            feature_lowering,
            feature_recipes,
        )

        rows: list[FeatureReport] = []
        surface = str(self.profile.surface)
        for feature in self.features:
            capability = self.profile.capabilities.features.get(feature)
            rows.append(
                FeatureReport(
                    feature=str(feature),
                    support=str(self.profile.support_for(feature)),
                    note=capability.note if capability is not None else None,
                    lowering=feature_lowering(
                        self.profile.provider,
                        surface,
                        feature,
                    ),
                    recipes=feature_recipes(
                        self.profile.provider,
                        surface,
                        feature,
                    ),
                    evidence=feature_evidence(
                        self.profile.provider,
                        surface,
                        feature,
                    ),
                )
            )
        return tuple(rows)

    def report(self, feature: Feature | str) -> FeatureReport | None:
        """Return the selected-surface support row for one requested feature."""

        feature_value = str(Feature(feature))
        for row in self.reports:
            if row.feature == feature_value:
                return row
        return None

    def raise_for_status(self) -> Plan:
        """Raise when the selected profile cannot satisfy the planned features."""

        if self.ok:
            return self
        if self.channel_mismatch and self.channel is not None:
            raise UnsupportedFeature(
                f"{self.profile.provider}:{self.profile.surface} is "
                f"{self.profile.channel}, not requested channel {self.channel}"
            )
        missing = ", ".join(str(feature) for feature in self.fit.missing)
        raise UnsupportedFeature(
            f"{self.profile.provider}:{self.profile.surface} does not support "
            f"required features: {missing}"
        )


class FeatureReport(YokeModel):
    """JSON-friendly support row for one feature."""

    feature: str
    support: str
    note: str | None = None
    lowering: str | None = None
    recipes: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


class Explanation(YokeModel):
    """Local explanation for how a Yoke call maps to one provider surface."""

    provider: str
    surface: str
    channel: str
    runnable: bool
    ok: bool
    features: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    model: Any
    reports: tuple[FeatureReport, ...] = ()

    def report(self, feature: Feature | str) -> FeatureReport | None:
        """Return the support row for one requested feature."""

        feature_value = str(Feature(feature))
        for row in self.reports:
            if row.feature == feature_value:
                return row
        return None

    @classmethod
    def from_plan(cls, plan: Plan, *, model: object) -> Explanation:
        """Build an explanation from a surface plan and model selection."""

        return cls(
            provider=str(plan.provider),
            surface=str(plan.surface),
            channel=str(plan.profile.channel),
            runnable=plan.profile.runnable,
            ok=plan.ok,
            features=tuple(str(feature) for feature in plan.features),
            missing=tuple(str(feature) for feature in plan.missing),
            model=model,
            reports=plan.reports,
        )


class SurfaceFeature(YokeModel):
    """One feature row annotated with its provider surface."""

    provider: str
    surface: str
    channel: str
    runtime: str
    runnable: bool = False
    feature: str
    support: str
    note: str | None = None
    lowering: str | None = None
    recipes: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


class SurfaceReport(YokeModel):
    """JSON-friendly provider surface capability report."""

    key: str
    provider: str
    surface: str
    channel: str
    runtime: str
    default: bool = False
    runnable: bool = False
    evidence: tuple[str, ...] = ()
    features: tuple[FeatureReport, ...] = ()

    def feature(self, feature: Feature | str) -> FeatureReport | None:
        """Return the report row for one feature on this surface."""

        feature_value = str(Feature(feature))
        for row in self.features:
            if row.feature == feature_value:
                return row
        return None

    def coverage(self) -> Coverage:
        """Return support-count coverage for this surface report."""

        return Coverage.from_supports(row.support for row in self.features)


class ProviderReport(YokeModel):
    """JSON-friendly capability matrix for one provider."""

    provider: str
    channel: str | None = None
    runnable: bool | None = None
    surfaces: tuple[SurfaceReport, ...] = ()

    def feature(self, feature: Feature | str) -> tuple[SurfaceFeature, ...]:
        """Return one feature across every surface in this provider report."""

        rows: list[SurfaceFeature] = []
        for surface in self.surfaces:
            row = surface.feature(feature)
            if row is None:
                continue
            rows.append(
                SurfaceFeature(
                    provider=surface.provider,
                    surface=surface.surface,
                    channel=surface.channel,
                    runtime=surface.runtime,
                    runnable=surface.runnable,
                    feature=row.feature,
                    support=row.support,
                    note=row.note,
                    lowering=row.lowering,
                    recipes=row.recipes,
                    evidence=row.evidence,
                )
            )
        return tuple(rows)

    def coverage(self) -> Coverage:
        """Return support-count coverage across all surfaces in this report."""

        return Coverage.from_supports(
            row.support for surface in self.surfaces for row in surface.features
        )
