"""Public Yoke models.

These are intentionally small first-pass Pydantic models. They define the public
language before provider adapters exist.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["claude", "codex"]


class YokeModel(BaseModel):
    """Base model for public Yoke configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Goal(YokeModel):
    """Session-attached objective state."""

    objective: str
    token_budget: int | None = None


class Skill(YokeModel):
    """Reusable capability loaded from text or a folder."""

    name: str | None = None
    path: Path | None = None
    instructions: str | None = None


class Agent(YokeModel):
    """Agent definition that can compile to Claude or Codex."""

    instructions: str | None = None
    description: str | None = None
    model: str | None = None
    effort: str | None = None
    goal: Goal | None = None
    skills: tuple[Skill, ...] = ()
    subagents: dict[str, "Agent"] = Field(default_factory=dict)
    workflows: dict[str, "Workflow"] = Field(default_factory=dict)


class Workflow(YokeModel):
    """Named orchestration recipe over agent calls."""

    name: str
    description: str | None = None


class Harness(YokeModel):
    """Binds an agent to a provider and working directory."""

    provider: Provider
    agent: Agent
    cwd: Path


class Session(YokeModel):
    """Provider session handle."""

    provider: Provider
    id: str
    goal: Goal | None = None


class Turn(YokeModel):
    """One input turn inside a session."""

    id: str | None = None
    prompt: str


class Event(YokeModel):
    """Normalized provider event."""

    kind: str
    message: str | None = None
    raw: object | None = None


class Run(YokeModel):
    """Convenience result for a one-shot run."""

    provider: Provider
    output: str | None = None
    events: tuple[Event, ...] = ()
