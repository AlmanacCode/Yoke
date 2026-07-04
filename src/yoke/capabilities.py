"""Provider capability language."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from yoke.models import YokeModel


class Feature(StrEnum):
    """Provider features Yoke knows how to reason about."""

    ONE_SHOT = "one_shot"
    SESSION = "session"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured_output"
    FILESYSTEM_AGENT = "filesystem_agent"
    INLINE_SUBAGENTS = "inline_subagents"
    DECLARED_SUBAGENTS = "declared_subagents"
    SKILLS = "skills"
    HOOKS = "hooks"
    MCP = "mcp"
    GOAL = "goal"
    MUTABLE_GOAL = "mutable_goal"
    WORKFLOW = "workflow"


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


class Capabilities(YokeModel):
    """Declared provider support matrix."""

    features: dict[Feature, Capability] = Field(default_factory=dict)

    def support_for(self, feature: Feature) -> Support:
        entry = self.features.get(feature)
        if entry is None:
            return Support.UNSUPPORTED
        return entry.support

    def supports(self, feature: Feature) -> bool:
        return self.support_for(feature) is not Support.UNSUPPORTED

    @classmethod
    def from_map(cls, features: dict[Feature, Support | tuple[Support, str]]) -> Capabilities:
        entries: dict[Feature, Capability] = {}
        for feature, value in features.items():
            if isinstance(value, tuple):
                support, note = value
            else:
                support, note = value, None
            entries[feature] = Capability(feature=feature, support=support, note=note)
        return cls(features=entries)
