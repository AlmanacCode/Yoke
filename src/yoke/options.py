"""Run-time options that live beside, not inside, agent definitions."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from yoke.models import Effort, Goal, Permissions, YokeModel


class RunOptions(YokeModel):
    """Options for one convenience run."""

    effort: Effort | str | None = None
    goal: Goal | None = None
    output_schema: dict[str, Any] | None = None
    max_turns: int | None = None
    permissions: Permissions | None = None
    provider: ProviderOptions | None = None


class SessionOptions(YokeModel):
    """Options for starting or resuming a session."""

    goal: Goal | None = None
    effort: Effort | str | None = None
    permissions: Permissions | None = None
    resume: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    provider: ProviderOptions | None = None


class WorkflowOptions(YokeModel):
    """Options for workflow orchestration."""

    concurrency: int = 4
    fail_fast: bool = True
    output_schema: dict[str, Any] | None = None


class ProviderOptions(YokeModel):
    """Escape hatch for provider-specific settings."""

    claude: dict[str, Any] = Field(default_factory=dict)
    codex: dict[str, Any] = Field(default_factory=dict)
