from __future__ import annotations

import threading

import pytest

from yoke.models import EventKind, RequestKind, ToolKind, ToolStatus
from yoke.policies import RequestPolicy
from yoke.providers.opencode import http
from yoke.providers.opencode.permissions import (
    OpencodePermissionWatchdog,
    permission_event,
    policy_response,
)

_RECORD = {
    "id": "per_abc",
    "sessionID": "ses_root",
    "permission": "bash",
    "patterns": ["echo hello"],
    "metadata": {"command": "echo hello"},
    "always": ["echo *"],
    "tool": {"messageID": "msg_1", "callID": "call_1"},
}


def test_permission_event_builds_provider_neutral_request() -> None:
    event = permission_event(_RECORD, "per_abc")

    assert event.kind == EventKind.APPROVAL_REQUEST
    assert event.tool_id == "per_abc"
    assert event.tool_name == "bash"
    assert event.tool is not None
    assert event.tool.kind == ToolKind.SHELL
    assert event.tool.command == "echo hello"
    assert event.tool.status == ToolStatus.STARTED
    assert event.request is not None
    assert event.request.kind == RequestKind.PERMISSION
    assert event.request.id == "per_abc"
    assert event.source_thread_id == "ses_root"
    # Defaults to deny so an unresolved permission fails closed.
    assert event.response is not None
    assert event.response.decision == "deny"


def test_policy_response_defaults_to_deny_without_a_handler() -> None:
    event = permission_event(_RECORD, "per_abc")

    response = policy_response(event, None)

    assert response.decision == "deny"


def test_policy_response_honors_an_allow_all_policy() -> None:
    event = permission_event(_RECORD, "per_abc")

    response = policy_response(event, RequestPolicy.allow_all())

    assert response.decision == "allow"


def test_policy_response_falls_back_to_default_when_handler_returns_none() -> None:
    event = permission_event(_RECORD, "per_abc")

    response = policy_response(event, lambda evt, default: None)

    assert response.decision == "deny"


def test_watchdog_resolves_a_pending_permission_and_emits_a_resolved_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http, "list_permissions", lambda base_url, timeout: (_RECORD,)
    )
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda base_url, permission_id, reply, timeout, **kwargs: replies.append(
            (permission_id, reply)
        ),
    )
    events = []
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=events.append,
        request_handler=RequestPolicy.allow_all(),
    )

    watchdog._poll_once()

    assert replies == [("per_abc", "once")]
    assert len(events) == 1
    assert events[0].kind == EventKind.REQUEST_RESOLVED
    assert events[0].response is not None
    assert events[0].response.decision == "allow"


def test_watchdog_denies_by_default_and_replies_reject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http, "list_permissions", lambda base_url, timeout: (_RECORD,)
    )
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda base_url, permission_id, reply, timeout, **kwargs: replies.append(
            (permission_id, reply)
        ),
    )
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=lambda event: None,
        request_handler=None,
    )

    watchdog._poll_once()

    assert replies == [("per_abc", "reject")]


def test_watchdog_ignores_permissions_from_other_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http, "list_permissions", lambda base_url, timeout: (_RECORD,)
    )
    resolved = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda *args, **kwargs: resolved.append(args),
    )
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_other",
        on_event=lambda event: None,
        request_handler=RequestPolicy.allow_all(),
    )

    watchdog._poll_once()

    assert resolved == []


def test_watchdog_does_not_re_resolve_an_already_seen_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http, "list_permissions", lambda base_url, timeout: (_RECORD,)
    )
    calls = []
    monkeypatch.setattr(
        http,
        "respond_permission",
        lambda *args, **kwargs: calls.append(args),
    )
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=lambda event: None,
        request_handler=RequestPolicy.allow_all(),
        seen_permission_ids={"per_abc"},
    )

    watchdog._poll_once()

    assert calls == []


def test_watchdog_run_stops_promptly_and_does_a_final_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polled = []
    monkeypatch.setattr(
        http,
        "list_permissions",
        lambda base_url, timeout: polled.append(1) or (),
    )
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=lambda event: None,
        request_handler=None,
        poll_interval_seconds=0.01,
    )
    stop_event = threading.Event()
    stop_event.set()

    watchdog.run(stop_event)

    assert len(polled) == 1


def test_watchdog_retries_a_permission_whose_reply_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: the ID used to be added to `_seen` before the reply was
    # attempted, so a transient respond_permission() failure was swallowed
    # and the permission was never retried — the in-flight message stayed
    # blocked until its own outer timeout instead of being re-resolved on
    # the next poll tick.
    monkeypatch.setattr(
        http, "list_permissions", lambda base_url, timeout: (_RECORD,)
    )
    attempts = []

    def flaky_respond(base_url, permission_id, reply, timeout, **kwargs):
        attempts.append(permission_id)
        if len(attempts) == 1:
            raise RuntimeError("transient network error")

    monkeypatch.setattr(http, "respond_permission", flaky_respond)
    events = []
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=events.append,
        request_handler=RequestPolicy.allow_all(),
    )

    watchdog._poll_once()
    assert attempts == ["per_abc"]
    assert events == []

    watchdog._poll_once()
    assert attempts == ["per_abc", "per_abc"]
    assert len(events) == 1


def test_watchdog_swallows_transient_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_list(base_url, timeout):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(http, "list_permissions", failing_list)
    watchdog = OpencodePermissionWatchdog(
        base_url="http://127.0.0.1:0",
        session_id="ses_root",
        on_event=lambda event: None,
        request_handler=None,
    )

    watchdog._poll_once()  # must not raise
