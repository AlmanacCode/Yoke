from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from yoke import Agent
from yoke.models import EventKind, Turn
from yoke.options import OpencodeOptions, ProviderOptions, RunOptions, SessionOptions
from yoke.policies import RequestPolicy
from yoke.providers.opencode import http
from yoke.providers.opencode_server import OpencodeServer, _OpencodeSession
from yoke.providers.runtime_deployment import deploy_runtime


@dataclass
class _FakeProcess:
    base_url: str = "http://127.0.0.1:0"

    def terminate(self) -> None:
        pass


def test_maybe_deploy_hook_bridge_returns_none_without_a_handler(
    tmp_path: Path,
) -> None:
    adapter = OpencodeServer()
    deployment = deploy_runtime(Agent(instructions="x"), "opencode", tmp_path)
    try:
        bridge = adapter._maybe_deploy_hook_bridge(SessionOptions(), deployment)
        assert bridge is None
        assert deployment.opencode_config_dir is None
    finally:
        deployment.cleanup()


def test_maybe_deploy_hook_bridge_writes_the_plugin_and_starts_a_server(
    tmp_path: Path,
) -> None:
    adapter = OpencodeServer()
    deployment = deploy_runtime(Agent(instructions="x"), "opencode", tmp_path)
    try:
        options = SessionOptions(
            provider=ProviderOptions(
                opencode=OpencodeOptions(policy=RequestPolicy.allow_all())
            )
        )
        bridge = adapter._maybe_deploy_hook_bridge(options, deployment)
        assert bridge is not None
        assert deployment.opencode_config_dir is not None
        plugin_path = (
            deployment.opencode_config_dir / "plugin" / "yoke_tool_hook.js"
        )
        assert plugin_path.is_file()
        assert "tool.execute.before" in plugin_path.read_text()
        assert bridge.base_url.startswith("http://127.0.0.1:")
    finally:
        bridge.stop()
        deployment.cleanup()


def test_resolve_hook_request_routes_to_the_sessions_own_policy_and_emits(
    tmp_path: Path,
) -> None:
    adapter = OpencodeServer()
    events = []
    internal = _OpencodeSession(
        process=_FakeProcess(),
        session_id="ses_test123",
        cwd=Path.cwd(),
        environment=None,
        db_path=tmp_path / "opencode.db",
        provider_options=OpencodeOptions(policy=RequestPolicy.deny_all("no")),
        current_emit=events.append,
    )
    adapter._sessions["ses_test123"] = internal

    response = adapter._resolve_hook_request(
        "ses_test123",
        {"sessionID": "ses_test123", "callID": "call_1", "tool": "bash", "args": {}},
    )

    assert response.decision == "deny"
    assert len(events) == 1
    assert events[0].kind == EventKind.REQUEST_RESOLVED
    assert events[0].response is response


def test_resolve_hook_request_defaults_to_allow_for_an_unknown_session() -> None:
    adapter = OpencodeServer()

    response = adapter._resolve_hook_request(
        "ses_unknown",
        {"sessionID": "ses_unknown", "callID": "call_1", "tool": "bash", "args": {}},
    )

    assert response.decision == "allow"


def test_send_intercepts_a_tool_call_via_a_live_hook_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exercises the real OpencodeHookBridge HTTP round trip (not a mocked
    # http.list_permissions-style stub) by having the fake post_message
    # itself act like the generated plugin: POST to the bridge's real
    # base_url mid-turn, the way `tool.execute.before` would.
    import httpx

    captured_reply = {}

    def fake_post_message(
        base_url, session_id, cwd, provider_id, model_id, prompt, timeout
    ):
        reply = httpx.post(
            f"{base_url}/tool-hook",
            json={
                "sessionID": session_id,
                "callID": "call_1",
                "tool": "bash",
                "args": {"command": "echo hi"},
            },
            timeout=5,
        ).json()
        captured_reply.update(reply)
        return {"info": {}, "parts": []}

    monkeypatch.setattr(http, "post_message", fake_post_message)

    adapter = OpencodeServer(poll_interval_seconds=0.01)
    deployment = deploy_runtime(Agent(instructions="x"), "opencode", tmp_path)
    try:
        options = SessionOptions(
            provider=ProviderOptions(
                opencode=OpencodeOptions(
                    policy=RequestPolicy.deny_tools("shell", message="no shell")
                )
            )
        )
        bridge = adapter._maybe_deploy_hook_bridge(options, deployment)
        assert bridge is not None
        internal = _OpencodeSession(
            process=type("P", (), {"base_url": bridge.base_url})(),
            session_id="ses_hooktest",
            cwd=tmp_path,
            environment=None,
            db_path=tmp_path / "opencode.db",
            provider_options=OpencodeOptions(
                policy=RequestPolicy.deny_tools("shell", message="no shell")
            ),
        )
        adapter._sessions["ses_hooktest"] = internal

        run = adapter._send(
            internal, turn=Turn(prompt="hi"), model="openai/gpt-5", options=RunOptions()
        )
    finally:
        bridge.stop()
        deployment.cleanup()

    assert captured_reply["deny"] is True
    assert captured_reply["message"] == "no shell"
    resolved = [e for e in run.events if e.kind == EventKind.REQUEST_RESOLVED]
    assert len(resolved) == 1
    assert resolved[0].response.decision == "deny"
