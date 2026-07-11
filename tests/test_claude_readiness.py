from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from yoke import Agent, Harness
from yoke.providers import claude as claude_provider
from yoke.readiness import CommandCheck


def test_claude_readiness_parses_json_auth_status(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", ModuleType("claude_agent_sdk"))

    async def fake_run_command(*args, env=None):
        return CommandCheck(
            code=0,
            stdout=(
                "{\n"
                '  "loggedIn": true,\n'
                '  "authMethod": "claude.ai",\n'
                '  "apiProvider": "firstParty"\n'
                "}"
            ),
            stderr="",
        )

    monkeypatch.setattr(claude_provider, "run_command", fake_run_command)
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    readiness = harness.check_sync()

    assert readiness.available is True
    assert readiness.message == "Claude authenticated via claude.ai"


def test_claude_auth_status_message_falls_back_for_non_json() -> None:
    assert claude_provider.claude_auth_status_message("authenticated") is None
