from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from yoke import Agent, Harness
from yoke.models import Access, Approval, Permissions
from yoke.options import ForkOptions, OpencodeOptions, ProviderOptions, SessionOptions
from yoke.policies import RequestPolicy
from yoke.providers.opencode import http
from yoke.providers.opencode_server import (
    OpencodeServer,
    _OpencodeSession,
    _resolved_permissions,
    _session_permission_block,
    opencode_options,
    opencode_options_for_run,
)


def test_session_permission_block_asks_for_approval_permissions() -> None:
    # Default Permissions() is access=READ, network=False, so the base "ask"
    # rule is followed by denies for every tool that access/network don't
    # cover — this is the fix for the reviewed gap where only `approval` was
    # translated and `Permissions(access=READ, network=False, approval=ASK)`
    # used to produce a bare `* = ask` with everything else still runnable.
    assert _session_permission_block(Permissions(approval=Approval.ASK)) == (
        {"permission": "*", "pattern": "*", "action": "ask"},
        {"permission": "write", "pattern": "*", "action": "deny"},
        {"permission": "edit", "pattern": "*", "action": "deny"},
        {"permission": "apply_patch", "pattern": "*", "action": "deny"},
        {"permission": "bash", "pattern": "*", "action": "deny"},
        {"permission": "webfetch", "pattern": "*", "action": "deny"},
        {"permission": "websearch", "pattern": "*", "action": "deny"},
    )


@pytest.mark.parametrize("approval", [Approval.AUTO, Approval.NEVER])
def test_session_permission_block_allows_all_for_full_access_and_network(
    approval: Approval,
) -> None:
    permissions = Permissions(
        approval=approval, access=Access.FULL, network=True
    )
    assert _session_permission_block(permissions) == http.OPENCODE_ALLOW_ALL_PERMISSION


@pytest.mark.parametrize("approval", [Approval.AUTO, Approval.NEVER])
def test_session_permission_block_still_denies_by_access_when_not_asking(
    approval: Approval,
) -> None:
    # AUTO/NEVER only mean "don't ask" — they must not also bypass the
    # access/network-derived denies, which are a separate safety boundary.
    permissions = Permissions(approval=approval, access=Access.READ, network=False)
    block = _session_permission_block(permissions)
    assert block[0] == {"permission": "*", "pattern": "*", "action": "allow"}
    denied = {rule["permission"] for rule in block[1:]}
    assert denied == {"write", "edit", "apply_patch", "bash", "webfetch", "websearch"}


def test_session_permission_block_write_access_allows_edit_but_not_bash() -> None:
    block = _session_permission_block(
        Permissions(approval=Approval.NEVER, access=Access.WRITE, network=True)
    )
    denied = {rule["permission"] for rule in block[1:]}
    assert denied == {"bash"}


def test_resolved_permissions_prefers_run_then_harness_then_agent() -> None:
    agent_permissions = Permissions(access=Access.READ)
    harness_permissions = Permissions(access=Access.WRITE)
    run_permissions = Permissions(access=Access.FULL)
    harness = Harness(
        provider="opencode",
        agent=Agent(instructions="x", permissions=agent_permissions),
        cwd=Path.cwd(),
        permissions=harness_permissions,
    )

    assert _resolved_permissions(harness, SessionOptions()) is harness_permissions
    assert (
        _resolved_permissions(
            harness, SessionOptions(permissions=run_permissions)
        )
        is run_permissions
    )

    bare_harness = Harness(
        provider="opencode",
        agent=Agent(instructions="x", permissions=agent_permissions),
        cwd=Path.cwd(),
    )
    assert _resolved_permissions(bare_harness, SessionOptions()) is agent_permissions


def test_opencode_options_helpers_read_provider_dot_opencode() -> None:
    policy = RequestPolicy.allow_all()
    session_options = SessionOptions(
        provider=ProviderOptions(opencode=OpencodeOptions(policy=policy))
    )
    assert opencode_options(session_options).policy is policy
    assert opencode_options(SessionOptions()) == {}
    assert opencode_options_for_run(SessionOptions()) is None  # type: ignore[arg-type]


@dataclass
class _FakeProcess:
    base_url: str = "http://127.0.0.1:0"
    terminated: bool = False

    def terminate(self) -> None:
        self.terminated = True


def test_start_session_passes_ask_all_permission_block_for_approval_ask(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        lambda *args, **kwargs: _FakeProcess(),
    )

    def fake_create_session(base_url, cwd_directory, title, timeout, *, permission):
        captured["permission"] = permission
        return {"id": "ses_test"}

    monkeypatch.setattr(http, "create_session", fake_create_session)

    permissions = Permissions(approval=Approval.ASK, access=Access.FULL, network=True)
    harness = Harness(
        provider="opencode",
        agent=Agent(instructions="x", permissions=permissions),
        cwd=tmp_path / "workspace",
    )
    adapter = OpencodeServer()
    from yoke.providers.runtime_deployment import deploy_runtime

    deployment = deploy_runtime(harness.agent, "opencode", tmp_path)
    try:
        adapter._start_session(harness, SessionOptions(), deployment)
    finally:
        deployment.cleanup()

    assert captured["permission"] == http.OPENCODE_ASK_ALL_PERMISSION


def test_fork_carries_over_the_parents_permission_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        adapter = OpencodeServer()
        process = _FakeProcess()
        policy = RequestPolicy.allow_all()

        def start_session(harness, options, deployment):
            return _OpencodeSession(
                process=process,
                session_id="parent",
                cwd=harness.cwd,
                environment=None,
                db_path=tmp_path / "opencode.db",
                provider_options=OpencodeOptions(policy=policy),
            )

        def fake_fork_session(base_url, session_id, timeout, message_id=None):
            return {"id": "forked"}

        adapter._start_session = start_session  # type: ignore[method-assign]
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.fork_session", fake_fork_session
        )
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.update_session_permission",
            lambda *args, **kwargs: {},
        )
        harness = Harness(
            provider="opencode",
            agent=Agent(instructions="be helpful"),
            cwd=tmp_path / "workspace",
            runtime_root=tmp_path / "runtime",
        )

        parent = await adapter.start(harness, SessionOptions())
        forked = await adapter.fork(parent, ForkOptions())

        forked_internal = adapter._sessions[forked.id]
        assert forked_internal.provider_options is not None
        assert forked_internal.provider_options.policy is policy

        await adapter.close(forked)
        await adapter.close(parent)

    asyncio.run(exercise())


def test_fork_reapplies_the_parents_permission_ruleset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Regression: OpenCode's POST /session/:id/fork does not inherit the
    # parent's permission ruleset (confirmed live) — a forked session starts
    # with none at all (default allow), silently dropping whatever
    # restriction the parent enforced even though the returned
    # Session.permissions still reports the parent's posture.
    async def exercise() -> None:
        adapter = OpencodeServer()
        process = _FakeProcess()

        def start_session(harness, options, deployment):
            return _OpencodeSession(
                process=process,
                session_id="parent",
                cwd=harness.cwd,
                environment=None,
                db_path=tmp_path / "opencode.db",
            )

        def fake_fork_session(base_url, session_id, timeout, message_id=None):
            return {"id": "forked"}

        captured: dict[str, object] = {}

        def fake_update_permission(base_url, session_id, timeout, *, permission):
            captured["session_id"] = session_id
            captured["permission"] = permission
            return {}

        adapter._start_session = start_session  # type: ignore[method-assign]
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.fork_session", fake_fork_session
        )
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.update_session_permission",
            fake_update_permission,
        )
        harness = Harness(
            provider="opencode",
            agent=Agent(
                instructions="be helpful",
                permissions=Permissions(
                    access=Access.READ, network=False, approval=Approval.NEVER
                ),
            ),
            cwd=tmp_path / "workspace",
            runtime_root=tmp_path / "runtime",
        )

        parent = await adapter.start(harness, SessionOptions())
        forked = await adapter.fork(parent, ForkOptions())

        assert captured["session_id"] == "forked"
        assert captured["permission"] == _session_permission_block(parent.permissions)

        await adapter.close(forked)
        await adapter.close(parent)

    asyncio.run(exercise())
