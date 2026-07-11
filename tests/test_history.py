from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from yoke import (
    Agent,
    Feature,
    Harness,
    Session,
    SessionHistory,
    SessionList,
    SessionMessage,
    SessionSummary,
    Support,
    clear_adapters,
    register,
)
from yoke.capabilities import Capabilities
from yoke.providers.claude import Claude
from yoke.providers.codex_app_server import CodexAppServer


class HistoryAdapter:
    provider = "codex"
    surface = "history_test"
    capabilities = Capabilities.from_map(
        {
            Feature.SESSION_LIST: Support.NATIVE,
            Feature.SESSION_READ: Support.NATIVE,
            Feature.SESSION_RENAME: Support.NATIVE,
            Feature.SESSION_TAG: Support.NATIVE,
        }
    )

    def __init__(self) -> None:
        self.list_limit: int | None = None
        self.read_id: str | None = None
        self.renamed: tuple[str, str] | None = None
        self.tagged: tuple[str, str | None] | None = None

    async def list_sessions(self, harness, *, limit, cursor, cwd, include_worktrees):
        self.list_limit = limit
        return SessionList(
            provider="codex",
            surface=self.surface,
            sessions=(
                SessionSummary(provider="codex", surface=self.surface, id="thread-1"),
            ),
        )

    async def read_session(
        self,
        harness,
        session_id,
        *,
        include_messages,
        limit,
        offset,
    ):
        self.read_id = session_id
        return SessionHistory(
            provider="codex",
            surface=self.surface,
            session=SessionSummary(
                provider="codex",
                surface=self.surface,
                id=session_id,
            ),
            messages=(
                SessionMessage(
                    provider="codex",
                    surface=self.surface,
                    session_id=session_id,
                    role="assistant",
                    content="hello",
                ),
            ),
        )

    async def rename(self, session, title):
        self.renamed = (session.id, title)
        return SessionSummary(
            provider="codex",
            surface=self.surface,
            id=session.id,
            title=title,
        )

    async def tag(self, session, tag):
        self.tagged = (session.id, tag)
        return SessionSummary(
            provider="codex",
            surface=self.surface,
            id=session.id,
            tag=tag,
        )


def test_harness_history_methods_delegate_to_adapter() -> None:
    asyncio.run(run_harness_history_methods_delegate())


async def run_harness_history_methods_delegate() -> None:
    clear_adapters()
    adapter = register(HistoryAdapter())
    harness = Harness(
        provider="codex",
        surface="history_test",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    listed = await harness.sessions(limit=1)
    history = await harness.read_session("thread-1")
    renamed = await harness.rename_session("thread-1", "Bug bash")
    tagged = await harness.tag_session("thread-1", "needs-review")

    assert adapter.list_limit == 1
    assert adapter.read_id == "thread-1"
    assert adapter.renamed == ("thread-1", "Bug bash")
    assert adapter.tagged == ("thread-1", "needs-review")
    assert listed.sessions[0].id == "thread-1"
    assert history.messages[0].content == "hello"
    assert renamed.title == "Bug bash"
    assert tagged.tag == "needs-review"


def test_claude_history_uses_sdk_session_helpers(monkeypatch) -> None:
    sdk = SimpleNamespace(
        list_sessions=lambda **kwargs: [
            SimpleNamespace(
                session_id="claude-session",
                summary="summary",
                first_prompt="first",
                custom_title="title",
                tag="needs-review",
                cwd="/repo",
                created_at=1,
                last_modified=2,
            )
        ],
        get_session_info=lambda session_id, **kwargs: SimpleNamespace(
            session_id=session_id,
            summary="summary",
            first_prompt=None,
            custom_title=None,
            cwd="/repo",
            created_at=1,
            last_modified=2,
        ),
        get_session_messages=lambda session_id, **kwargs: [
            SimpleNamespace(
                session_id=session_id,
                uuid="msg-1",
                type="assistant",
                message={"content": "hello"},
            )
        ],
        rename_session=lambda session_id, title, **kwargs: None,
        tag_session=lambda session_id, tag, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path("/repo"),
    )
    adapter = Claude()

    listed = asyncio.run(adapter.list_sessions(harness, limit=1))
    history = asyncio.run(adapter.read_session(harness, "claude-session"))

    assert listed.sessions[0].title == "title"
    assert listed.sessions[0].tag == "needs-review"
    assert listed.sessions[0].provider_session_id == "claude-session"
    assert history.session.id == "claude-session"
    assert history.messages[0].role == "assistant"
    assert history.messages[0].content == {"content": "hello"}

    renamed = asyncio.run(
        adapter.rename(
            Session(
                provider="claude",
                surface="claude_python_sdk",
                id="claude-session",
                cwd=Path("/repo"),
            ),
            "Renamed session",
        )
    )
    tagged = asyncio.run(
        adapter.tag(
            Session(
                provider="claude",
                surface="claude_python_sdk",
                id="claude-session",
                cwd=Path("/repo"),
            ),
            "needs-review",
        )
    )

    assert renamed.title == "Renamed session"
    assert tagged.tag == "needs-review"


def test_codex_app_server_history_parses_thread_rpc(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_request_rpc(process, method, params, timeout):
        calls.append((method, params))
        if method == "thread/list":
            return {
                "data": [
                    {
                        "id": "thread-1",
                        "sessionId": "root-1",
                        "name": "Bug bash",
                        "preview": "Fix tests",
                        "createdAt": 1,
                        "updatedAt": 2,
                    }
                ],
                "nextCursor": "next",
            }
        if method == "thread/read":
            return {
                "thread": {
                    "id": "thread-1",
                    "name": "Bug bash",
                    "turns": [
                        {"id": "turn-1", "type": "user", "preview": "hi"},
                        {"id": "turn-2", "type": "assistant", "items": ["hello"]},
                    ],
                }
            }
        if method == "thread/name/set":
            return {"thread": {"id": params["threadId"], "name": params["name"]}}
        return {}

    monkeypatch.setattr(
        "yoke.providers.codex_app_server.request_rpc",
        fake_request_rpc,
    )
    adapter = CodexAppServer()
    process = object()

    listed = adapter._list_sessions(process, limit=1, cursor=None, cwd="/repo")
    history = adapter._read_session(
        process,
        "thread-1",
        include_messages=True,
        limit=1,
        offset=1,
    )
    renamed = adapter._rename_session(process, "thread-1", "Renamed")

    assert listed.sessions[0].id == "thread-1"
    assert listed.sessions[0].provider_session_id == "root-1"
    assert listed.next_cursor == "next"
    assert history.session.title == "Bug bash"
    assert history.messages[0].id == "turn-2"
    assert history.messages[0].content == ["hello"]
    assert renamed.title == "Renamed"
    assert ("thread/list", {"limit": 1, "cwd": "/repo"}) in calls
    assert (
        "thread/name/set",
        {"threadId": "thread-1", "name": "Renamed"},
    ) in calls
