from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yoke import (
    Agent,
    Event,
    Feature,
    ForkOptions,
    Goal,
    Harness,
    Permissions,
    Run,
    RunOptions,
    Session,
    SessionOptions,
    Support,
    register,
)
from yoke.capabilities import Capabilities
from yoke.errors import UnsupportedFeature


class SessionAdapter:
    provider = "codex"
    surface = "session_test"
    capabilities = Capabilities.from_map(
        {
            Feature.SESSION: Support.NATIVE,
            Feature.STREAMING: Support.NATIVE,
            Feature.GOAL: Support.NATIVE,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.INTERRUPT: Support.NATIVE,
            Feature.SESSION_COMPACT: Support.NATIVE,
            Feature.SESSION_RENAME: Support.NATIVE,
            Feature.SESSION_TAG: Support.NATIVE,
            Feature.FORK: Support.NATIVE,
        }
    )

    def __init__(self) -> None:
        self.options: list[RunOptions] = []
        self.closed: list[str] = []
        self.interrupted: list[str] = []
        self.compacted: list[str] = []
        self.renamed: list[tuple[str, str]] = []
        self.tagged: list[tuple[str, str | None]] = []
        self.forked: list[tuple[str, ForkOptions]] = []

    async def send(self, session, turn, options):
        self.options.append(options)
        return Run(provider="codex", output=turn.prompt)

    async def stream(self, session, turn, options):
        self.options.append(options)
        if False:
            yield None

    async def close(self, session):
        self.closed.append(session.id)

    async def interrupt(self, session):
        self.interrupted.append(session.id)

    async def compact(self, session):
        self.compacted.append(session.id)

    async def rename(self, session, title):
        self.renamed.append((session.id, title))
        from yoke import SessionSummary

        return SessionSummary(
            provider=self.provider,
            surface=self.surface,
            id=session.id,
            title=title,
        )

    async def tag(self, session, tag):
        self.tagged.append((session.id, tag))
        from yoke import SessionSummary

        return SessionSummary(
            provider=self.provider,
            surface=self.surface,
            id=session.id,
            tag=tag,
        )

    async def fork(self, session, options):
        self.forked.append((session.id, options))
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=f"{session.id}-fork",
            provider_session_id=session.provider_session_id,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions,
        )

    async def start(self, harness, options):
        self.options.append(options)
        return Session(
            provider=self.provider,
            surface=self.surface,
            id="started",
            agent=harness.agent,
            cwd=harness.cwd,
        )


class HarnessStreamAdapter(SessionAdapter):
    surface = "harness_stream_test"

    async def stream(self, session, turn, options):
        self.options.append(options)
        yield Event(kind="text", message=turn.prompt, surface=session.surface)

    async def start(self, harness, options):
        self.options.append(options)
        return Session(
            provider=self.provider,
            surface=self.surface,
            id="streamed",
            agent=harness.agent,
            cwd=harness.cwd,
            goal=options.resolve_goal(harness.agent.goal),
        )


def test_session_run_accepts_run_options() -> None:
    asyncio.run(run_session_options_check())


async def run_session_options_check() -> None:
    adapter = register(SessionAdapter())
    options = RunOptions(
        goal=Goal("One turn."),
        permissions=Permissions(network=True),
        output_schema={"type": "object", "title": "TurnSchema"},
    )
    session = Session(
        provider="codex",
        surface="session_test",
        id="thread",
        agent=Agent(instructions="test"),
    )

    result = await session.run("hello", options)

    assert result.output == "hello"
    assert adapter.options == [options]


def test_session_stream_accepts_run_options_sync() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    assert session.stream_sync("hello", RunOptions(inherit_goal=False)) == ()
    assert adapter.options[0].inherit_goal is False


def test_session_capabilities_still_use_surface_adapter() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    assert session.capabilities() is adapter.capabilities
    assert session.profile().supports(Feature.STREAMING)


def test_session_async_context_manager_closes_session() -> None:
    asyncio.run(run_session_async_context_check())


async def run_session_async_context_check() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    async with session as active:
        assert active is session

    assert adapter.closed == ["thread"]


def test_session_sync_context_manager_closes_session() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    with session as active:
        assert active is session

    assert adapter.closed == ["thread"]


def test_session_interrupt_delegates_to_surface_adapter() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    session.interrupt_sync()

    assert adapter.interrupted == ["thread"]


def test_session_compact_delegates_to_surface_adapter() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    session.compact_sync()

    assert adapter.compacted == ["thread"]


def test_session_compact_guards_capability() -> None:
    session = Session(provider="codex", surface="codex_cli", id="thread")

    with pytest.raises(UnsupportedFeature):
        session.compact_sync()


def test_session_rename_and_tag_delegate_to_surface_adapter() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")

    renamed = session.rename_sync("Bug bash")
    tagged = session.tag_sync(None)

    assert adapter.renamed == [("thread", "Bug bash")]
    assert adapter.tagged == [("thread", None)]
    assert renamed.title == "Bug bash"
    assert tagged.tag is None


def test_session_fork_delegates_to_surface_adapter() -> None:
    adapter = register(SessionAdapter())
    session = Session(provider="codex", surface="session_test", id="thread")
    options = ForkOptions(ephemeral=True, last_turn_id="turn-1")

    fork = session.fork_sync(options)

    assert fork.id == "thread-fork"
    assert adapter.forked == [("thread", options)]


def test_harness_async_session_context_starts_and_closes_session() -> None:
    asyncio.run(run_harness_async_session_context_check())


async def run_harness_async_session_context_check() -> None:
    adapter = register(SessionAdapter())
    options = SessionOptions(resume="thread")
    harness = Harness(
        provider="codex",
        surface="session_test",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    async with harness.session(options) as session:
        assert session.id == "started"

    assert adapter.options == [options]
    assert adapter.closed == ["started"]


def test_harness_sync_session_context_starts_and_closes_session() -> None:
    adapter = register(SessionAdapter())
    harness = Harness(
        provider="codex",
        surface="session_test",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    with harness.session_sync() as session:
        assert session.id == "started"

    assert len(adapter.options) == 1
    assert adapter.closed == ["started"]


def test_harness_stream_starts_streams_and_closes_session() -> None:
    asyncio.run(run_harness_stream_check())


async def run_harness_stream_check() -> None:
    adapter = register(HarnessStreamAdapter())
    agent_goal = Goal("Keep the one-turn stream goal-aware.")
    options = RunOptions(inherit_goal=True)
    harness = Harness(
        provider="codex",
        surface="harness_stream_test",
        agent=Agent(instructions="test", goal=agent_goal),
        cwd=Path.cwd(),
    )

    events = [event async for event in harness.stream("hello", options)]

    assert [event.message for event in events] == ["hello"]
    assert events[0].surface == "harness_stream_test"
    assert adapter.options[0].resolve_goal(agent_goal) == agent_goal
    assert adapter.options[1] is options
    assert adapter.closed == ["streamed"]


def test_harness_stream_sync_collects_events() -> None:
    adapter = register(HarnessStreamAdapter())
    harness = Harness(
        provider="codex",
        surface="harness_stream_test",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    events = harness.stream_sync("hello")

    assert tuple(event.message for event in events) == ("hello",)
    assert adapter.closed == ["streamed"]
