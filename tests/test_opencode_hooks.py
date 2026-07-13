from __future__ import annotations

import httpx

from yoke.models import EventKind, RequestKind, ToolKind
from yoke.policies import RequestPolicy
from yoke.providers.opencode.hooks import OpencodeHookBridge, hook_event, resolve

_PAYLOAD = {
    "sessionID": "ses_root",
    "callID": "call_1",
    "tool": "bash",
    "args": {"command": "echo hi", "workdir": "/tmp"},
}


def test_hook_event_builds_provider_neutral_tool_request() -> None:
    event = hook_event(_PAYLOAD)

    assert event.kind == EventKind.TOOL_REQUEST
    assert event.tool_id == "call_1"
    assert event.tool_name == "bash"
    assert event.tool is not None
    assert event.tool.kind == ToolKind.SHELL
    assert event.tool.command == "echo hi"
    assert event.request is not None
    assert event.request.kind == RequestKind.TOOL
    assert event.source_thread_id == "ses_root"
    # Opt-in-only feature: default is allow-unchanged, not deny.
    assert event.response is not None
    assert event.response.decision == "allow"


def test_resolve_defaults_to_allow_without_a_handler() -> None:
    event, response = resolve(_PAYLOAD, None)

    assert response.decision == "allow"
    assert response.updated_input is None


def test_resolve_honors_a_deny_all_policy() -> None:
    _, response = resolve(_PAYLOAD, RequestPolicy.deny_all("no bash"))

    assert response.decision == "deny"
    assert response.message == "no bash"


def test_resolve_can_return_updated_input_from_a_raw_handler() -> None:
    def handler(event, default):
        from yoke.models import Response

        return Response.allow(updated_input={"command": "echo modified"})

    _, response = resolve(_PAYLOAD, handler)

    assert response.decision == "allow"
    assert response.updated_input == {"command": "echo modified"}


def test_bridge_serializes_the_resolved_response_over_http() -> None:
    captured = {}

    def fake_resolve(session_id, payload):
        from yoke.models import Response

        captured["session_id"] = session_id
        captured["payload"] = payload
        return Response.allow(updated_input={"command": "echo modified"})

    bridge = OpencodeHookBridge(resolve=fake_resolve)
    bridge.start()
    try:
        response = httpx.post(f"{bridge.base_url}/tool-hook", json=_PAYLOAD, timeout=5)
        assert response.status_code == 200
        body = response.json()
        assert body["args"] == {"command": "echo modified"}
        assert body["deny"] is False
        assert captured["session_id"] == "ses_root"
        assert captured["payload"]["tool"] == "bash"
    finally:
        bridge.stop()


def test_bridge_reports_deny_and_message_over_http() -> None:
    def fake_resolve(session_id, payload):
        from yoke.models import Response

        return Response.deny("blocked")

    bridge = OpencodeHookBridge(resolve=fake_resolve)
    bridge.start()
    try:
        response = httpx.post(f"{bridge.base_url}/tool-hook", json=_PAYLOAD, timeout=5)
        body = response.json()
        assert body["deny"] is True
        assert body["message"] == "blocked"
    finally:
        bridge.stop()


def test_bridge_reports_a_visible_deny_instead_of_resetting_the_connection() -> None:
    # Regression: a bug in a caller's request_handler (or a
    # Response.updated_input value json.dumps can't serialize) used to
    # propagate out of do_POST uncaught, resetting the connection with no
    # response at all. The generated plugin's `await res.json()` then
    # throws, which — per tool.execute.before's own semantics — blocks the
    # tool call with no context and no REQUEST_RESOLVED event. A real HTTP
    # 200 with an honest deny message is strictly better: still fails
    # closed, but distinguishable from a genuine policy denial.
    def broken_resolve(session_id, payload):
        raise RuntimeError("handler exploded")

    bridge = OpencodeHookBridge(resolve=broken_resolve)
    bridge.start()
    try:
        response = httpx.post(f"{bridge.base_url}/tool-hook", json=_PAYLOAD, timeout=5)
        assert response.status_code == 200
        body = response.json()
        assert body["deny"] is True
        assert "handler exploded" in body["message"]
    finally:
        bridge.stop()
