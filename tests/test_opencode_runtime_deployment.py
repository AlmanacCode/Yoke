from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yoke import Agent, Harness, Skill
from yoke.errors import YokeError
from yoke.options import ForkOptions, SessionOptions
from yoke.providers.opencode import http
from yoke.providers.opencode_server import OpencodeServer, _OpencodeSession
from yoke.providers.runtime_deployment import deploy_runtime


def agent_with_skill() -> Agent:
    return Agent(
        instructions="be helpful",
        skills=(Skill.from_text("check sources", name="sources"),),
    )


class FakeOpencodeProcess:
    def __init__(self) -> None:
        self.base_url = "http://127.0.0.1:0"
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_opencode_runtime_compiles_native_skill(tmp_path: Path) -> None:
    deployment = deploy_runtime(agent_with_skill(), "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is not None
        skill_file = deployment.opencode_config_dir / "skills" / "sources" / "SKILL.md"
        assert skill_file.is_file()
    finally:
        deployment.cleanup()
    assert not deployment.root.exists()


def test_opencode_runtime_skips_config_dir_without_skills(tmp_path: Path) -> None:
    deployment = deploy_runtime(Agent(instructions="none"), "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is None
    finally:
        deployment.cleanup()


def test_opencode_runtime_writes_caller_supplied_plugin_source(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="x",
        options={
            "opencode_plugins": {
                "my_plugin": "export const MyPlugin = async () => ({});"
            }
        },
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is not None
        plugin_path = deployment.opencode_config_dir / "plugin" / "my_plugin.js"
        assert plugin_path.is_file()
        assert plugin_path.read_text() == "export const MyPlugin = async () => ({});"
    finally:
        deployment.cleanup()


def test_opencode_runtime_ignores_non_string_plugin_entries(tmp_path: Path) -> None:
    agent = Agent(
        instructions="x",
        options={"opencode_plugins": {"bad": 123, "ok": "export const X = 1;"}},
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is not None
        plugin_dir = deployment.opencode_config_dir / "plugin"
        assert not (plugin_dir / "bad.js").exists()
        assert (plugin_dir / "ok.js").is_file()
    finally:
        deployment.cleanup()


def test_opencode_runtime_compiles_mcp_servers_into_config_content(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="be helpful",
        options={
            "mcp_servers": {
                "docs": {
                    "type": "remote",
                    "url": "https://developers.example.com/mcp",
                }
            }
        },
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        assert deployment.opencode_config_content == (
            '{"mcp": {"docs": {"type": "remote", '
            '"url": "https://developers.example.com/mcp"}}}'
        )
    finally:
        deployment.cleanup()


def test_opencode_runtime_skips_config_content_without_mcp_servers(
    tmp_path: Path,
) -> None:
    deployment = deploy_runtime(agent_with_skill(), "opencode", tmp_path)
    try:
        assert deployment.opencode_config_content is None
    finally:
        deployment.cleanup()


def test_opencode_runtime_compiles_direct_subagent_as_filesystem_agent(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="root",
        subagents={
            "reviewer": Agent(
                description="Find correctness issues.",
                instructions="Review the patch for bugs.",
            )
        },
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is not None
        agent_file = deployment.opencode_config_dir / "agents" / "reviewer.md"
        assert agent_file.is_file()
        text = agent_file.read_text()
        assert 'description: "Find correctness issues."' in text
        assert "mode: subagent" in text
        assert "Review the patch for bugs." in text
    finally:
        deployment.cleanup()


def test_opencode_runtime_sets_config_dir_for_subagents_without_skills(
    tmp_path: Path,
) -> None:
    agent = Agent(
        instructions="root",
        subagents={"reviewer": Agent(instructions="review")},
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        assert deployment.opencode_config_dir is not None
    finally:
        deployment.cleanup()


def test_opencode_runtime_rejects_colliding_subagent_filenames(tmp_path: Path) -> None:
    # Regression: two subagent names that slugify to the same
    # agents/<name>.md path used to silently overwrite one another with no
    # error — _write_codex already guards the equivalent case for Codex.
    agent = Agent(
        instructions="root",
        subagents={
            "code review": Agent(instructions="a"),
            "code-review": Agent(instructions="b"),
        },
    )
    with pytest.raises(YokeError):
        deploy_runtime(agent, "opencode", tmp_path)


def test_opencode_shared_process_keeps_runtime_until_last_release(
    tmp_path: Path,
) -> None:
    adapter = OpencodeServer()
    process = FakeOpencodeProcess()
    deployment = deploy_runtime(agent_with_skill(), "opencode", tmp_path)
    adapter._deployments[id(process)] = deployment
    adapter._retain_process(process)
    adapter._retain_process(process)

    adapter._release_process(process)
    assert deployment.root.exists()
    assert not process.terminated

    adapter._release_process(process)
    assert not deployment.root.exists()
    assert process.terminated


def test_opencode_adapter_cleans_runtime_on_close(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = OpencodeServer()
        process = FakeOpencodeProcess()

        def start_session(harness, options, deployment):
            return _OpencodeSession(
                process=process,
                session_id="session-1",
                cwd=harness.cwd,
                environment=None,
                db_path=tmp_path / "opencode.db",
                instructions=harness.agent.instructions,
            )

        adapter._start_session = start_session  # type: ignore[method-assign]
        runtime_root = tmp_path / "runtime"
        harness = Harness(
            provider="opencode",
            agent=agent_with_skill(),
            cwd=tmp_path / "workspace",
            runtime_root=runtime_root,
        )

        session = await adapter.start(harness, SessionOptions())
        assert list(runtime_root.iterdir())
        assert adapter._deployments

        await adapter.close(session)
        assert not list(runtime_root.iterdir())
        assert process.terminated

    asyncio.run(exercise())


def test_opencode_closing_a_fork_does_not_delete_the_parents_live_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Regression: fork() used to store `deployment=None` on the forked
    # session's own dataclass field, and close() cleaned up whichever
    # session object happened to hold a deployment reference. Closing a
    # fork while the parent (sharing the same live process) was still open
    # worked by accident only because the fork's own deployment was None;
    # closing the *parent* first while a fork was still open would delete
    # the skills directory the still-running shared process depends on.
    # Deployment cleanup must be tied to the process refcount, not to
    # either session object.
    async def exercise() -> None:
        adapter = OpencodeServer()
        process = FakeOpencodeProcess()

        def start_session(harness, options, deployment):
            return _OpencodeSession(
                process=process,
                session_id="parent",
                cwd=harness.cwd,
                environment=None,
                db_path=tmp_path / "opencode.db",
                instructions=harness.agent.instructions,
            )

        def fake_fork_session(base_url, session_id, timeout, message_id=None):
            return {"id": "forked"}

        adapter._start_session = start_session  # type: ignore[method-assign]
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.fork_session", fake_fork_session
        )
        runtime_root = tmp_path / "runtime"
        harness = Harness(
            provider="opencode",
            agent=agent_with_skill(),
            cwd=tmp_path / "workspace",
            runtime_root=runtime_root,
        )

        parent = await adapter.start(harness, SessionOptions())
        forked = await adapter.fork(parent, ForkOptions())
        assert list(runtime_root.iterdir())

        # Close the parent first — the fork is still open and shares the
        # same process, so the runtime must survive.
        await adapter.close(parent)
        assert list(runtime_root.iterdir())
        assert not process.terminated

        await adapter.close(forked)
        assert not list(runtime_root.iterdir())
        assert process.terminated

    asyncio.run(exercise())


def test_opencode_fork_carries_over_parent_instructions_marked_as_sent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Regression: fork() previously omitted `instructions`/`instructions_sent`
    # entirely, so a forked session's first send() would look like
    # instructions were never sent (instructions_sent defaults to False)
    # while also never actually sending them, since the parent's
    # instructions were dropped rather than copied over.
    async def exercise() -> None:
        adapter = OpencodeServer()
        process = FakeOpencodeProcess()

        def start_session(harness, options, deployment):
            return _OpencodeSession(
                process=process,
                session_id="parent",
                cwd=harness.cwd,
                environment=None,
                db_path=tmp_path / "opencode.db",
                instructions=harness.agent.instructions,
            )

        def fake_fork_session(base_url, session_id, timeout, message_id=None):
            return {"id": "forked"}

        adapter._start_session = start_session  # type: ignore[method-assign]
        monkeypatch.setattr(
            "yoke.providers.opencode_server.http.fork_session", fake_fork_session
        )
        harness = Harness(
            provider="opencode",
            agent=agent_with_skill(),
            cwd=tmp_path / "workspace",
            runtime_root=tmp_path / "runtime",
        )

        parent = await adapter.start(harness, SessionOptions())
        forked = await adapter.fork(parent, ForkOptions())

        forked_internal = adapter._sessions[forked.id]
        assert forked_internal.instructions == "be helpful"
        assert forked_internal.instructions_sent is True

        await adapter.close(forked)
        await adapter.close(parent)

    asyncio.run(exercise())


def test_opencode_start_session_passes_mcp_config_content_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}

    def fake_start_opencode_server(command, cwd, timeout, env=None):
        captured_env.update(env or {})
        return FakeOpencodeProcess()

    monkeypatch.setattr(
        "yoke.providers.opencode_server.start_opencode_server",
        fake_start_opencode_server,
    )
    monkeypatch.setattr(
        http, "create_session", lambda *args, **kwargs: {"id": "ses_test"}
    )

    agent = Agent(
        instructions="be helpful",
        options={
            "mcp_servers": {
                "docs": {"type": "remote", "url": "https://example.com/mcp"}
            }
        },
    )
    deployment = deploy_runtime(agent, "opencode", tmp_path)
    try:
        harness = Harness(
            provider="opencode",
            agent=agent,
            cwd=tmp_path / "workspace",
        )
        adapter = OpencodeServer()
        adapter._start_session(harness, SessionOptions(), deployment)
        assert (
            captured_env["OPENCODE_CONFIG_CONTENT"]
            == deployment.opencode_config_content
        )
    finally:
        deployment.cleanup()
