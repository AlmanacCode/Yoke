"""Provider ports.

Yoke's domain language depends on these protocols. Claude and Codex adapters
implement them outside the core model layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from yoke.capabilities import Capabilities
from yoke.models import Event, Goal, Harness, Provider, Run, Session, Surface, Turn
from yoke.options import RunOptions, SessionOptions


class ProviderAdapter(Protocol):
    """Concrete provider boundary implemented by Claude and Codex adapters."""

    provider: Provider
    surface: Surface | str
    capabilities: Capabilities

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        """Execute one convenience run."""

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        """Start or resume a provider session."""

    async def send(self, session: Session, turn: Turn) -> Run:
        """Send one turn to a session and collect a result."""

    async def stream(self, session: Session, turn: Turn) -> AsyncIterator[Event]:
        """Send one turn and stream normalized events."""

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        """Attach or update a session goal."""

    async def clear_goal(self, session: Session) -> Session:
        """Clear a session goal."""

    async def close(self, session: Session) -> None:
        """Release provider resources for a session."""
