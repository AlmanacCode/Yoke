from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from yoke.models import EventKind, Turn
from yoke.options import RunOptions
from yoke.providers.opencode import http
from yoke.providers.opencode_server import OpencodeServer, _OpencodeSession


@dataclass
class _FakeProcess:
    base_url: str = "http://127.0.0.1:0"


def test_send_emits_provider_session_event_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: Run.provider_session_id scans events in reverse for one
    # carrying provider_session_id. Without emitting this event, CodeAlmanac
    # (and any other Yoke consumer) can never populate a transcript
    # reference for an opencode run — confirmed missing during the
    # slice-143 codealmanac integration pass.
    monkeypatch.setattr(
        http,
        "post_message",
        lambda *args, **kwargs: {
            "info": {"tokens": {"input": 1, "output": 1, "total": 2}},
            "parts": [{"type": "text", "text": "hello"}],
        },
    )
    server = OpencodeServer()
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        deployment=None,
        db_path=tmp_path / "opencode.db",
    )

    run = server._send(
        internal, turn=Turn(prompt="hi"), model="openai/gpt-5", options=RunOptions()
    )

    assert run.events[0].kind == EventKind.PROVIDER_SESSION
    assert run.events[0].provider_session_id == "ses_test123"
    assert run.provider_session_id == "ses_test123"
    assert run.output == "hello"


def test_send_prepends_agent_instructions_on_first_turn_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: OpenCode's session/message API has no dedicated system-
    # prompt field, unlike Claude/Codex. Without prepending Agent.instructions
    # to the first turn, the model never receives its actual task
    # description — confirmed live against a real CodeAlmanac build run,
    # which produced only a generic clarifying question instead of doing
    # any work.
    sent_prompts: list[str] = []

    def fake_post_message(
        base_url, session_id, cwd, provider_id, model_id, prompt, timeout
    ):
        sent_prompts.append(prompt)
        return {"info": {}, "parts": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(http, "post_message", fake_post_message)
    server = OpencodeServer()
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        deployment=None,
        db_path=tmp_path / "opencode.db",
        instructions="You are a careful maintainer.",
    )

    server._send(
        internal,
        turn=Turn(prompt="turn one"),
        model="openai/gpt-5",
        options=RunOptions(),
    )
    server._send(
        internal,
        turn=Turn(prompt="turn two"),
        model="openai/gpt-5",
        options=RunOptions(),
    )

    assert "You are a careful maintainer." in sent_prompts[0]
    assert "turn one" in sent_prompts[0]
    assert sent_prompts[1] == "turn two"
    assert "You are a careful maintainer." not in sent_prompts[1]
