from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from yoke import (
    Agent,
    Feature,
    Goal,
    GoalLoopOptions,
    GoalRun,
    Harness,
    Run,
    RunOptions,
    Session,
    SessionOptions,
    Support,
    clear_adapters,
    register,
)
from yoke.capabilities import Capabilities
from yoke.providers.codex import Codex
from yoke.providers.codex_app_server import CodexAppServer


class FakeGoalLoopAdapter:
    provider = "codex"
    surface = "fake-goal-loop"
    capabilities = Capabilities.from_map({Feature.GOAL_LOOP: Support.NATIVE})

    def __init__(self) -> None:
        self.options: list[GoalLoopOptions] = []

    async def goal_loop(self, harness, options):
        self.options.append(options)
        session = Session(
            provider="codex",
            surface="fake-goal-loop",
            id="goal-thread-1",
            agent=harness.agent,
            cwd=harness.cwd,
            goal=options.goal,
        )
        return GoalRun(
            provider="codex",
            surface="fake-goal-loop",
            goal=options.goal,
            session=session,
        )


def test_run_options_inherit_agent_goal_by_default() -> None:
    goal = Goal("Ship safely.")

    assert RunOptions().resolve_goal(goal) == goal


def test_run_options_can_disable_agent_goal_inheritance() -> None:
    goal = Goal("Ship safely.")

    assert RunOptions(inherit_goal=False).resolve_goal(goal) is None


def test_explicit_run_goal_wins_over_inheritance_policy() -> None:
    agent_goal = Goal("Default goal.")
    turn_goal = Goal("This turn only.")

    assert (
        RunOptions(goal=turn_goal, inherit_goal=False).resolve_goal(agent_goal)
        == turn_goal
    )


def test_session_options_can_disable_agent_goal_inheritance() -> None:
    assert SessionOptions(inherit_goal=False).resolve_goal(Goal("Default.")) is None


def test_harness_goal_loop_delegates_to_selected_provider_surface() -> None:
    asyncio.run(run_harness_goal_loop_delegation_check())


async def run_harness_goal_loop_delegation_check() -> None:
    clear_adapters()
    fake = register(FakeGoalLoopAdapter())
    goal = Goal("Keep working until verified.")
    harness = Harness(
        provider="codex",
        surface="fake-goal-loop",
        agent=Agent(instructions="Coordinate."),
        cwd=Path.cwd(),
    )

    result = await harness.goal_loop(GoalLoopOptions(goal=goal))

    assert result.ok is True
    assert result.provider == "codex"
    assert result.surface == "fake-goal-loop"
    assert result.goal == goal
    assert result.session.id == "goal-thread-1"
    assert result.session.goal == goal
    assert result.auto_continues is True
    assert fake.options == [GoalLoopOptions(goal=goal)]


def test_codex_app_server_goal_loop_returns_session_handle() -> None:
    asyncio.run(run_codex_app_server_goal_loop_check())


async def run_codex_app_server_goal_loop_check() -> None:
    captured: dict[str, Any] = {}
    adapter = CodexAppServer()
    goal = Goal("Finish safely.")

    async def fake_start(harness, options):
        captured["options"] = options
        return Session(
            provider="codex",
            surface="codex_app_server",
            id="thread-1",
            agent=harness.agent,
            cwd=harness.cwd,
            goal=options.goal,
        )

    adapter.start = fake_start  # type: ignore[method-assign]
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="Coordinate."),
        cwd=Path.cwd(),
    )

    result = await adapter.goal_loop(harness, GoalLoopOptions(goal=goal))

    assert result.provider == "codex"
    assert result.surface == "codex_app_server"
    assert result.goal == goal
    assert result.session.id == "thread-1"
    assert result.session.goal == goal
    assert result.auto_continues is True
    assert captured["options"] == SessionOptions(
        goal=goal,
        inherit_goal=False,
    )


def test_codex_run_can_disable_agent_goal_inheritance() -> None:
    asyncio.run(run_codex_goal_inheritance_check())


async def run_codex_goal_inheritance_check() -> None:
    captured: dict[str, Any] = {}
    codex = Codex()

    async def fake_run_turn(**kwargs: Any) -> Run:
        captured.update(kwargs)
        return Run(provider="codex", output="ok")

    codex._run_turn = fake_run_turn  # type: ignore[method-assign]
    agent = Agent(
        instructions="Coordinate.",
        goal=Goal("Do not inherit this goal."),
    )

    await codex.run(
        Harness(provider="codex", surface="codex_cli", agent=agent, cwd=Path.cwd()),
        "ordinary run",
        RunOptions(inherit_goal=False),
    )

    assert captured["goal"] is None


def test_codex_app_server_run_can_disable_agent_goal_inheritance() -> None:
    asyncio.run(run_codex_app_server_goal_inheritance_check())


async def run_codex_app_server_goal_inheritance_check() -> None:
    captured: dict[str, Any] = {}
    adapter = CodexAppServer()

    async def fake_start(harness, options):
        captured["goal"] = options.resolve_goal(harness.agent.goal)
        return "session"

    async def fake_send(session, turn, *, output_schema=None, options=None):
        return Run(provider="codex", output="ok")

    async def fake_close(session):
        return None

    adapter.start = fake_start  # type: ignore[method-assign]
    adapter._send = fake_send  # type: ignore[method-assign]
    adapter.close = fake_close  # type: ignore[method-assign]
    agent = Agent(
        instructions="Coordinate.",
        goal=Goal("Do not inherit this app-server goal."),
    )

    await adapter.run(
        Harness(
            provider="codex",
            surface="codex_app_server",
            agent=agent,
            cwd=Path.cwd(),
        ),
        "ordinary run",
        RunOptions(inherit_goal=False),
    )

    assert captured["goal"] is None
