from __future__ import annotations

import asyncio
from pathlib import Path

from yoke import Agent, Harness, RunOptions, RunStatus
from yoke.providers.codex import Codex
from yoke.providers.codex_app.events import TurnResult, read_turn_step


class FakeCodexCli:
    async def run(self, **kwargs):
        yield {"type": "thread.started", "thread_id": "thread-1"}
        yield {
            "type": "turn.failed",
            "error": {"message": "model refused the request"},
        }


class FakeAppServerProcess:
    def read_until(self, deadline: float, timeout_label: str):
        return {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "turn": {"error": {"message": "provider turn failed"}},
            },
        }


def test_codex_cli_turn_failure_returns_failed_run() -> None:
    asyncio.run(run_codex_cli_failure_check())


async def run_codex_cli_failure_check() -> None:
    adapter = Codex()
    adapter.cli = FakeCodexCli()
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    result = await adapter.run(harness, "do the thing", options=RunOptions())

    assert result.status is RunStatus.FAILED
    assert result.surface == "codex_cli"
    assert result.events[0].surface == "codex_cli"
    assert result.failure is not None
    assert result.failure.message == "model refused the request"
    assert result.session is not None
    assert result.session.id == "thread-1"


def test_codex_app_turn_error_marks_result_failure() -> None:
    turn = TurnResult()

    step = read_turn_step(
        FakeAppServerProcess(),
        "thread-1",
        "turn-1",
        turn,
        deadline=999999999.0,
    )

    assert step.done is True
    assert turn.failure is not None
    assert turn.failure.message == "provider turn failed"
    assert step.events[-1].kind == "error"
