"""Codex adapter placeholder.

The TypeScript Codex SDK and app-server expose the right primitives, but the
Python adapter needs a deliberate bridge rather than a fake wrapper.
"""

from __future__ import annotations

from yoke.capabilities import Capabilities, Feature, Support
from yoke.errors import UnsupportedFeature
from yoke.models import Event, Goal, Harness, Provider, Run, Session, Turn
from yoke.options import RunOptions, SessionOptions


class Codex:
    """Capability declaration for Codex."""

    provider: Provider = "codex"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.STREAMING: Support.NATIVE,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.FILESYSTEM_AGENT: Support.COMPILED,
            Feature.INLINE_SUBAGENTS: Support.NATIVE,
            Feature.DECLARED_SUBAGENTS: Support.NATIVE,
            Feature.SKILLS: Support.NATIVE,
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: Support.NATIVE,
            Feature.MUTABLE_GOAL: Support.NATIVE,
            Feature.WORKFLOW: Support.EMULATED,
        }
    )

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")

    async def send(self, session: Session, turn: Turn) -> Run:
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")

    async def stream(self, session: Session, turn: Turn):
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")
        yield Event(kind="unreachable")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Codex goal bridge is the next provider slice.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Codex goal bridge is the next provider slice.")
