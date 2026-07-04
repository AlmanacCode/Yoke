"""Public Yoke language.

The models in this module are intentionally provider-neutral. Claude and Codex
mechanics belong behind provider ports, not in these objects.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provider = Literal["claude", "codex"]
Surface = Literal[
    "claude_python_sdk",
    "claude_cli",
    "codex_cli",
    "codex_typescript_sdk",
    "codex_app_server",
]


class YokeModel(BaseModel):
    """Base model for public Yoke values."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


class Effort(StrEnum):
    """Provider-neutral effort hint."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


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


class GoalStatus(StrEnum):
    """Provider-neutral goal status."""

    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    USAGE_LIMITED = "usage_limited"
    BUDGET_LIMITED = "budget_limited"
    COMPLETE = "complete"


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


class Skill(YokeModel):
    """Reusable capability loaded from text or a folder."""

    name: str | None = None
    path: Path | None = None
    instructions: str | None = None

    @classmethod
    def from_path(cls, path: str | Path, name: str | None = None) -> Skill:
        return cls(path=Path(path), name=name)

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

    @model_validator(mode="after")
    def require_useful_body(self) -> Agent:
        if self.instructions is None and self.description is None:
            raise ValueError("agent needs instructions or description")
        return self


class Step(YokeModel):
    """One workflow step."""

    name: str
    agent: str
    prompt: str
    depends_on: tuple[str, ...] = ()
    output_schema: dict[str, Any] | None = None


class Workflow(YokeModel):
    """Named orchestration recipe over agent calls."""

    name: str
    description: str | None = None
    steps: tuple[Step, ...] = ()


class Harness(YokeModel):
    """Binds an agent to a provider and working directory.

    The public object has methods because the common case should read well:
    `await Harness(...).run("...")`. Provider mechanics still live behind the
    adapter port.
    """

    provider: Provider
    surface: Surface | str | None = None
    agent: Agent
    cwd: Path
    permissions: Permissions | None = None

    def with_adapter(self, adapter: Any) -> Harness:
        """Register an adapter and return this harness.

        This keeps examples readable while still letting embedded apps own
        adapter construction explicitly.
        """

        from yoke.adapters import register

        register(adapter)
        return self

    async def run(self, prompt: str, options: Any | None = None) -> Run:
        """Execute one convenience run."""

        from yoke.adapters import adapter_for
        from yoke.options import RunOptions

        run_options = options if isinstance(options, RunOptions) else RunOptions()
        return await adapter_for(self.provider, self.surface).run(self, prompt, run_options)

    async def start(self, options: Any | None = None) -> Session:
        """Start or resume a provider session."""

        from yoke.adapters import adapter_for
        from yoke.options import SessionOptions

        session_options = (
            options if isinstance(options, SessionOptions) else SessionOptions()
        )
        return await adapter_for(self.provider, self.surface).start(self, session_options)


class Session(YokeModel):
    """Provider session handle."""

    provider: Provider
    id: str
    goal: Goal | None = None


class Turn(YokeModel):
    """One input turn inside a session."""

    prompt: str
    id: str | None = None


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
    session: Session | None = None
    usage: dict[str, Any] | None = None
