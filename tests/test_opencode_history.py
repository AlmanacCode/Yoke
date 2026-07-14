from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from yoke import Agent, Harness
from yoke.errors import UnsupportedFeature
from yoke.providers.opencode import http
from yoke.providers.opencode_server import OpencodeServer


@dataclass
class _FakeProcess:
    base_url: str = "http://127.0.0.1:0"

    def terminate(self) -> None:
        pass


def _harness(tmp_path: Path) -> Harness:
    return Harness(
        provider="opencode",
        agent=Agent(instructions="x"),
        cwd=tmp_path,
    )


def test_list_sessions_rejects_cursor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    adapter = OpencodeServer()
    with pytest.raises(UnsupportedFeature):
        asyncio.run(adapter.list_sessions(_harness(tmp_path), cursor="abc"))


def test_list_sessions_rejects_excluding_worktrees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    adapter = OpencodeServer()
    with pytest.raises(UnsupportedFeature):
        asyncio.run(
            adapter.list_sessions(_harness(tmp_path), include_worktrees=False)
        )


def test_list_sessions_passes_explicit_cwd_as_directory_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    captured: dict[str, object] = {}

    def fake_list_sessions(base_url, timeout, *, directory=None):
        captured["directory"] = directory
        return ({"id": "ses_1", "title": "one"},)

    monkeypatch.setattr(http, "list_sessions", fake_list_sessions)
    adapter = OpencodeServer()

    result = asyncio.run(
        adapter.list_sessions(_harness(tmp_path), cwd=tmp_path / "other")
    )

    assert captured["directory"] == str(tmp_path / "other")
    assert result.sessions[0].id == "ses_1"


def test_list_sessions_does_not_filter_by_directory_when_cwd_omitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    captured: dict[str, object] = {}

    def fake_list_sessions(base_url, timeout, *, directory=None):
        captured["directory"] = directory
        return ()

    monkeypatch.setattr(http, "list_sessions", fake_list_sessions)
    adapter = OpencodeServer()

    asyncio.run(adapter.list_sessions(_harness(tmp_path)))

    assert captured["directory"] is None


def test_read_session_fetches_messages_via_the_history_api_and_slices_locally(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        http, "read_session", lambda base_url, session_id, timeout: {"id": session_id}
    )
    entries = tuple(
        {"info": {"id": f"msg_{i}", "role": "user"}} for i in range(5)
    )
    calls: list[str] = []

    def fake_list_messages(base_url, session_id, timeout):
        calls.append(session_id)
        return entries

    monkeypatch.setattr(http, "list_messages", fake_list_messages)
    adapter = OpencodeServer()

    history = asyncio.run(
        adapter.read_session(
            _harness(tmp_path), "ses_1", limit=2, offset=1
        )
    )

    assert calls == ["ses_1"]
    assert [m.id for m in history.messages] == ["msg_1", "msg_2"]


def test_read_session_skips_messages_when_not_requested(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        http, "read_session", lambda base_url, session_id, timeout: {"id": session_id}
    )
    called = []
    monkeypatch.setattr(
        http,
        "list_messages",
        lambda *args, **kwargs: called.append(1) or (),
    )
    adapter = OpencodeServer()

    history = asyncio.run(
        adapter.read_session(_harness(tmp_path), "ses_1", include_messages=False)
    )

    assert called == []
    assert history.messages == ()
