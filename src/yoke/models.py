"""Public Yoke language.

The models in this module are intentionally provider-neutral. Claude and Codex
mechanics belong behind provider ports, not in these objects.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provider = Literal["claude", "codex"]
Surface = Literal[
    "claude_python_sdk",
    "claude_cli",
    "codex_cli",
    "codex_typescript_sdk",
    "codex_app_server",
]
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


class StepResult(YokeModel):
    """Result for one workflow step."""

    step: str
    run: Run


class WorkflowRun(YokeModel):
    """Result for a workflow execution."""

    workflow: str
    steps: tuple[StepResult, ...] = ()
    output: str | None = None


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

    def run_sync(self, prompt: str, options: Any | None = None) -> Run:
        """Execute one convenience run from synchronous code."""

        return run_blocking(lambda: self.run(prompt, options))

    async def start(self, options: Any | None = None) -> Session:
        """Start or resume a provider session."""

        from yoke.adapters import adapter_for
        from yoke.options import SessionOptions

        session_options = (
            options if isinstance(options, SessionOptions) else SessionOptions()
        )
        return await adapter_for(self.provider, self.surface).start(self, session_options)

    def start_sync(self, options: Any | None = None) -> Session:
        """Start or resume a provider session from synchronous code."""

        return run_blocking(lambda: self.start(options))

    async def workflow(
        self,
        workflow: Workflow | str,
        prompt: str = "",
        options: Any | None = None,
    ) -> WorkflowRun:
        """Run a Yoke workflow."""

        from yoke.options import WorkflowOptions
        from yoke.workflows import run_workflow

        workflow_options = (
            options if isinstance(options, WorkflowOptions) else WorkflowOptions()
        )
        selected = self.agent.workflows[workflow] if isinstance(workflow, str) else workflow
        return await run_workflow(self, selected, prompt, workflow_options)

    def workflow_sync(
        self,
        workflow: Workflow | str,
        prompt: str = "",
        options: Any | None = None,
    ) -> WorkflowRun:
        """Run a Yoke workflow from synchronous code."""

        return run_blocking(lambda: self.workflow(workflow, prompt, options))


class Session(YokeModel):
    """Runtime session handle.

    `Session` is serializable enough to resume simple providers, but adapters
    may keep live provider state behind the handle.
    """

    provider: Provider
    surface: Surface | str | None = None
    id: str
    agent: Agent | None = None
    cwd: Path | None = None
    permissions: Permissions | None = None
    goal: Goal | None = None

    async def run(self, prompt: str) -> Run:
        """Send one turn and collect the result."""

        from yoke.adapters import adapter_for

        return await adapter_for(self.provider, self.surface).send(
            self, Turn(prompt=prompt)
        )

    def run_sync(self, prompt: str) -> Run:
        """Send one turn from synchronous code."""

        return run_blocking(lambda: self.run(prompt))

    async def stream(self, prompt: str) -> AsyncIterator[Event]:
        """Send one turn and stream normalized events."""

        from yoke.adapters import adapter_for

        async for event in adapter_for(self.provider, self.surface).stream(
            self, Turn(prompt=prompt)
        ):
            yield event

    def stream_sync(self, prompt: str) -> tuple[Event, ...]:
        """Collect stream events from synchronous code."""

        return run_blocking(lambda: collect_events(self.stream(prompt)))

    async def get_goal(self) -> Goal | None:
        """Read provider goal state when supported."""

        from yoke.adapters import adapter_for

        return await adapter_for(self.provider, self.surface).get_goal(self)

    def get_goal_sync(self) -> Goal | None:
        """Read provider goal state from synchronous code."""

        return run_blocking(lambda: self.get_goal())

    async def set_goal(self, goal: Goal) -> Session:
        """Attach or update a provider goal and return the updated session."""

        from yoke.adapters import adapter_for

        return await adapter_for(self.provider, self.surface).set_goal(self, goal)

    def set_goal_sync(self, goal: Goal) -> Session:
        """Attach or update a provider goal from synchronous code."""

        return run_blocking(lambda: self.set_goal(goal))

    async def clear_goal(self) -> Session:
        """Clear provider goal state and return the updated session."""

        from yoke.adapters import adapter_for

        return await adapter_for(self.provider, self.surface).clear_goal(self)

    def clear_goal_sync(self) -> Session:
        """Clear provider goal state from synchronous code."""

        return run_blocking(lambda: self.clear_goal())

    async def close(self) -> None:
        """Release provider resources for this session."""

        from yoke.adapters import adapter_for

        await adapter_for(self.provider, self.surface).close(self)

    def close_sync(self) -> None:
        """Release provider resources from synchronous code."""

        return run_blocking(lambda: self.close())


class Turn(YokeModel):
    """One input turn inside a session."""

    prompt: str
    id: str | None = None


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
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    total_tokens: int | None = None
    total_processed_tokens: int | None = None
    max_tokens: int | None = None


class Event(YokeModel):
    """Normalized provider event."""

    kind: str
    message: str | None = None
    tool_id: str | None = None
    tool_name: str | None = None
    tool_input: str | None = None
    tool: Tool | None = None
    tool_result: Any | None = None
    tool_is_error: bool | None = None
    usage: Usage | None = None
    provider_session_id: str | None = None
    provider_event_id: str | None = None
    provider_parent_tool_use_id: str | None = None
    source_thread_id: str | None = None
    source_turn_id: str | None = None
    raw: object | None = None


class Run(YokeModel):
    """Convenience result for a one-shot run."""

    provider: Provider
    output: str | None = None
    events: tuple[Event, ...] = ()
    session: Session | None = None
    usage: Usage | dict[str, Any] | None = None
