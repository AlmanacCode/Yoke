"""Provider ports.

Yoke's domain language depends on these protocols. Claude and Codex adapters
implement them outside the core model layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from yoke.capabilities import Capabilities
from yoke.models import (
    Event,
    Goal,
    GoalRun,
    Harness,
    Login,
    Model,
    Provider,
    Readiness,
    Run,
    Session,
    SessionHistory,
    SessionList,
    SessionSummary,
    Surface,
    Turn,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    ForkOptions,
    GoalLoopOptions,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
)


class ProviderAdapter(Protocol):
    """Concrete provider boundary implemented by Claude and Codex adapters."""

    provider: Provider
    surface: Surface | str
    capabilities: Capabilities

    async def check(self, harness: Harness) -> Readiness:
        """Return local readiness without starting an agent run."""

    async def login(
        self,
        harness: Harness,
        method: str,
        *,
        api_key: str | None = None,
    ) -> Login:
        """Start a provider-native login flow when supported."""

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        """Execute one convenience run."""

    async def models(self, harness: Harness) -> tuple[Model, ...]:
        """List provider models when supported."""

    async def workflow(
        self,
        harness: Harness,
        workflow: Workflow,
        prompt: str,
        options: WorkflowOptions,
    ) -> WorkflowRun:
        """Execute a provider-native workflow."""

    async def goal_loop(
        self,
        harness: Harness,
        options: GoalLoopOptions,
    ) -> GoalRun:
        """Start a provider-owned keep-working goal loop."""

    async def list_sessions(
        self,
        harness: Harness,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        cwd: str | None = None,
        include_worktrees: bool = True,
    ) -> SessionList:
        """List stored provider sessions without starting or resuming one."""

    async def read_session(
        self,
        harness: Harness,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        """Read stored provider session history without resuming it."""

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        """Start or resume a provider session."""

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        """Send one turn to a session and collect a result."""

    async def stream(
        self,
        session: Session,
        turn: Turn,
        options: RunOptions,
    ) -> AsyncIterator[Event]:
        """Send one turn and stream normalized events."""

    async def get_goal(self, session: Session) -> Goal | None:
        """Read provider goal state when the surface supports it."""

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        """Attach or update a session goal."""

    async def clear_goal(self, session: Session) -> Session:
        """Clear a session goal."""

    async def interrupt(self, session: Session) -> None:
        """Request interruption of the active session turn."""

    async def compact(self, session: Session) -> None:
        """Request provider-native compaction of a session."""

    async def rename(self, session: Session, title: str) -> SessionSummary:
        """Rename a provider session."""

    async def tag(self, session: Session, tag: str | None) -> SessionSummary:
        """Tag or untag a provider session."""

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        """Branch a provider session when the surface supports it."""

    async def close(self, session: Session) -> None:
        """Release provider resources for a session."""
