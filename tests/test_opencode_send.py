from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from yoke.errors import YokeError
from yoke.models import EventKind, RunStatus, Turn
from yoke.options import OpencodeOptions, ProviderOptions, RunOptions
from yoke.policies import RequestPolicy
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
        db_path=tmp_path / "opencode.db",
    )

    run = server._send(
        internal, turn=Turn(prompt="hi"), model="openai/gpt-5", options=RunOptions()
    )

    assert run.events[0].kind == EventKind.PROVIDER_SESSION
    assert run.events[0].provider_session_id == "ses_test123"
    assert run.provider_session_id == "ses_test123"
    assert run.output == "hello"


def test_send_passes_agent_instructions_as_system_on_first_turn_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # OpenCode's POST /session/:id/message has a documented `system` field
    # (confirmed live, v1.17.15) — Agent.instructions goes through it rather
    # than being prepended to the prompt text, keeping system and user
    # content separate. Sent only on the session's first turn, matching the
    # once-per-session semantics Claude/Codex use for their own native
    # system-prompt fields.
    sent: list[tuple[str, str | None]] = []

    def fake_post_message(
        base_url,
        session_id,
        cwd,
        provider_id,
        model_id,
        prompt,
        timeout,
        *,
        system=None,
    ):
        sent.append((prompt, system))
        return {"info": {}, "parts": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(http, "post_message", fake_post_message)
    server = OpencodeServer()
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
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

    assert sent[0] == ("turn one", "You are a careful maintainer.")
    assert sent[1] == ("turn two", None)
    assert internal.instructions_sent is True


def test_send_keeps_instructions_unsent_when_the_first_post_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: instructions_sent used to become True before the HTTP
    # request succeeded, so a failed first send lost the instructions on
    # retry — the model's very first real turn would run with no system
    # prompt at all.
    def failing_post_message(*args, **kwargs):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(http, "post_message", failing_post_message)
    server = OpencodeServer()
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
        instructions="You are a careful maintainer.",
    )

    run = server._send(
        internal,
        turn=Turn(prompt="turn one"),
        model="openai/gpt-5",
        options=RunOptions(),
    )

    assert run.status == RunStatus.FAILED
    assert internal.instructions_sent is False

    sent: list[tuple[str, str | None]] = []

    def fake_post_message(
        base_url,
        session_id,
        cwd,
        provider_id,
        model_id,
        prompt,
        timeout,
        *,
        system=None,
    ):
        sent.append((prompt, system))
        return {"info": {}, "parts": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(http, "post_message", fake_post_message)
    server._send(
        internal,
        turn=Turn(prompt="retry"),
        model="openai/gpt-5",
        options=RunOptions(),
    )

    assert sent == [("retry", "You are a careful maintainer.")]


def test_send_resolves_a_pending_permission_via_the_run_level_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http,
        "post_message",
        lambda *args, **kwargs: {"info": {}, "parts": []},
    )
    monkeypatch.setattr(
        http,
        "list_permissions",
        lambda base_url, timeout: (
            {
                "id": "per_1",
                "sessionID": "ses_test123",
                "permission": "bash",
                "metadata": {"command": "echo hi"},
            },
        ),
    )
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda base_url, permission_id, reply, timeout, **kwargs: replies.append(
            (permission_id, reply)
        ),
    )
    server = OpencodeServer(poll_interval_seconds=0.01)
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
    )

    run = server._send(
        internal,
        turn=Turn(prompt="hi"),
        model="openai/gpt-5",
        options=RunOptions(
            provider=ProviderOptions(
                opencode=OpencodeOptions(policy=RequestPolicy.allow_all())
            )
        ),
    )

    assert replies == [("per_1", "once")]
    resolved = [e for e in run.events if e.kind == EventKind.REQUEST_RESOLVED]
    assert len(resolved) == 1
    assert resolved[0].response is not None
    assert resolved[0].response.decision == "allow"


def test_send_falls_back_to_the_session_level_policy_set_at_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http,
        "post_message",
        lambda *args, **kwargs: {"info": {}, "parts": []},
    )
    monkeypatch.setattr(
        http,
        "list_permissions",
        lambda base_url, timeout: (
            {"id": "per_2", "sessionID": "ses_test123", "permission": "bash"},
        ),
    )
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda base_url, permission_id, reply, timeout, **kwargs: replies.append(
            (permission_id, reply)
        ),
    )
    server = OpencodeServer(poll_interval_seconds=0.01)
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
        provider_options=OpencodeOptions(policy=RequestPolicy.allow_all()),
    )

    server._send(
        internal, turn=Turn(prompt="hi"), model="openai/gpt-5", options=RunOptions()
    )

    assert replies == [("per_2", "once")]


def _make_db(path: Path) -> None:
    import sqlite3

    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT, "
        "time_created INTEGER)"
    )
    connection.execute(
        "CREATE TABLE part (id TEXT PRIMARY KEY, session_id TEXT, message_id TEXT, "
        "data TEXT, time_created INTEGER)"
    )
    connection.commit()
    connection.close()


def _insert_stuck_tool_part(path: Path, *, session_id: str) -> None:
    import json
    import sqlite3

    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT OR IGNORE INTO message (id, session_id, data, time_created) "
        "VALUES (?, ?, ?, ?)",
        ("m1", session_id, json.dumps({"role": "assistant"}), 1),
    )
    stuck_start_ms = int((time.time() - 10_000) * 1000)
    connection.execute(
        "INSERT INTO part (id, session_id, message_id, data, time_created) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            "p1",
            session_id,
            "m1",
            json.dumps(
                {
                    "type": "tool",
                    "tool": "bash",
                    "state": {"status": "running", "time": {"start": stuck_start_ms}},
                }
            ),
            1,
        ),
    )
    connection.commit()
    connection.close()


def test_send_reacts_to_a_stuck_tool_call_by_terminating_and_returning_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression/coverage gap: only the watchdog itself was tested for
    # stuck-tool-call detection in isolation. This exercises _send's actual
    # reaction — stop the watchdog, terminate the process, classify the
    # failure, and return a FAILED Run — which was previously untested at
    # the adapter level.
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_stuck_tool_part(db_path, session_id="ses_stuck")

    class _TrackingProcess:
        def __init__(self) -> None:
            self.base_url = "http://127.0.0.1:0"
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True

    def hanging_post_message(*args, **kwargs):
        # Blocks long enough for the watchdog (polling every 0.01s with a
        # 0.01s stuck threshold against an already-old part row) to detect
        # the stuck state and cause _send to unwind before this returns.
        time.sleep(2)
        return {"info": {}, "parts": []}

    monkeypatch.setattr(http, "post_message", hanging_post_message)
    server = OpencodeServer(
        poll_interval_seconds=0.01,
        stuck_after_seconds=0.01,
    )
    process = _TrackingProcess()
    internal = _OpencodeSession(
        process=process,
        session_id="ses_stuck",
        cwd=Path.cwd(),
        environment=None,
        db_path=db_path,
    )

    run = server._send(
        internal, turn=Turn(prompt="hi"), model="openai/gpt-5", options=RunOptions()
    )

    assert run.status == RunStatus.FAILED
    assert run.failure is not None
    assert process.terminated is True


def test_stream_yields_events_live_and_ends_without_a_final_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http,
        "post_message",
        lambda *args, **kwargs: {
            "info": {"tokens": {"input": 1, "output": 1, "total": 2}},
            "parts": [{"type": "text", "text": "hello"}],
        },
    )
    server = OpencodeServer()
    session_id = "ses_stream"
    server._sessions[session_id] = _OpencodeSession(
        process=_FakeProcess(),
        session_id=session_id,
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
    )
    session = _session_for(server, session_id)

    async def exercise() -> list:
        events = []
        async for event in server.stream(
            session, Turn(prompt="hi"), RunOptions(model="openai/gpt-5")
        ):
            events.append(event)
        return events

    events = asyncio.run(exercise())
    assert events[0].kind == EventKind.PROVIDER_SESSION
    assert events[0].provider_session_id == session_id


def test_stream_raises_on_failure_instead_of_silently_ending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_post_message(*args, **kwargs):
        raise RuntimeError("opencode request failed")

    monkeypatch.setattr(http, "post_message", failing_post_message)
    server = OpencodeServer()
    session_id = "ses_stream_fail"
    server._sessions[session_id] = _OpencodeSession(
        process=_FakeProcess(),
        session_id=session_id,
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
    )
    session = _session_for(server, session_id)

    async def exercise() -> None:
        async for _event in server.stream(
            session, Turn(prompt="hi"), RunOptions(model="openai/gpt-5")
        ):
            pass

    with pytest.raises(YokeError):
        asyncio.run(exercise())


def _session_for(server: OpencodeServer, session_id: str):
    from yoke.models import Session

    return Session(
        provider=server.provider,
        surface=server.surface,
        id=session_id,
        provider_session_id=session_id,
    )
