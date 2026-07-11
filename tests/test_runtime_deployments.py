from __future__ import annotations

import asyncio
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from yoke import Agent, Harness, Skill
from yoke.errors import YokeError
from yoke.models import Permissions
from yoke.options import SessionOptions
from yoke.providers.codex_app_server import (
    AppServerThread,
    CodexAppServer,
    codex_runtime_config,
    config_overrides,
    merged_runtime_config,
    thread_params,
)
from yoke.providers.runtime_deployment import deploy_runtime


def agent_with_native_features(secret: str = "child-only") -> Agent:
    return Agent(
        instructions="parent-only",
        skills=(Skill.from_text("check sources", name="sources"),),
        subagents={
            "reviewer": Agent(
                description="Review changes.",
                instructions=secret,
                model="gpt-5.4-mini",
            )
        },
    )


def test_runtime_root_is_runtime_only(tmp_path: Path) -> None:
    cwd = tmp_path / "workspace"
    harness = Harness(
        provider="codex",
        agent=agent_with_native_features(),
        cwd=cwd,
        runtime_root=tmp_path / "runtime",
    )

    assert "runtime_root" not in harness.model_dump()
    assert str(tmp_path / "runtime") not in repr(harness)


@pytest.mark.parametrize("relative", [Path("."), Path(".yoke/runtime")])
def test_runtime_root_must_be_outside_cwd(tmp_path: Path, relative: Path) -> None:
    cwd = tmp_path / "workspace"
    with pytest.raises(ValueError, match="runtime_root must be outside cwd"):
        Harness(
            provider="codex",
            agent=agent_with_native_features(),
            cwd=cwd,
            runtime_root=cwd / relative,
        )


def test_codex_runtime_compiles_absolute_agent_and_native_skill(tmp_path: Path) -> None:
    deployment = deploy_runtime(agent_with_native_features(), "codex", tmp_path)
    try:
        config = deployment.codex_agents["reviewer"]
        agent_file = Path(config["config_file"])

        assert agent_file.is_absolute()
        assert agent_file.parent != tmp_path
        assert "child-only" in agent_file.read_text()
        assert deployment.generated_skill_root is not None
        assert (deployment.generated_skill_root / "sources" / "SKILL.md").is_file()
    finally:
        deployment.cleanup()
    assert not deployment.root.exists()


def test_claude_runtime_compiles_only_inline_skills(tmp_path: Path) -> None:
    deployment = deploy_runtime(agent_with_native_features(), "claude", tmp_path)
    try:
        plugin = deployment.claude_plugin_root
        assert plugin is not None
        assert (plugin / ".claude-plugin" / "plugin.json").is_file()
        assert (plugin / "skills" / "sources" / "SKILL.md").is_file()
        assert not (plugin / "agents").exists()
    finally:
        deployment.cleanup()


def test_same_named_concurrent_deployments_are_isolated(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(
            pool.map(
                lambda _: deploy_runtime(
                    agent_with_native_features(), "codex", tmp_path
                ),
                range(2),
            )
        )
    try:
        assert first.root != second.root
        assert first.codex_agents["reviewer"] != second.codex_agents["reviewer"]
    finally:
        first.cleanup()
        second.cleanup()


def test_codex_runtime_rejects_colliding_role_artifacts(tmp_path: Path) -> None:
    agent = Agent(
        instructions="parent",
        subagents={
            "first": Agent(instructions="first", options={"codex_name": "same role"}),
            "second": Agent(instructions="second", options={"codex_name": "same-role"}),
        },
    )

    with pytest.raises(YokeError, match="colliding role names or artifact paths"):
        deploy_runtime(agent, "codex", tmp_path)
    assert not list(tmp_path.iterdir())


def test_codex_role_skills_and_nested_roles_preserve_ownership(tmp_path: Path) -> None:
    agent = Agent(
        instructions="parent",
        skills=(Skill.from_text("ROOT_SECRET", name="root-skill"),),
        subagents={
            "reviewer": Agent(
                instructions="review",
                skills=(Skill.from_text("CHILD_SECRET", name="child-skill"),),
                subagents={
                    "critic": Agent(
                        instructions="NESTED_SECRET",
                        options={"codex_name": "native-critic"},
                    )
                },
            )
        },
    )
    deployment = deploy_runtime(agent, "codex", tmp_path)
    try:
        assert (deployment.generated_skill_root / "root-skill" / "SKILL.md").exists()
        assert not (deployment.generated_skill_root / "child-skill").exists()
        reviewer = Path(
            deployment.codex_agents["reviewer"]["config_file"]
        ).read_text()
        critic = Path(
            deployment.codex_agents["native-critic"]["config_file"]
        ).read_text()
        assert "role-skills/reviewer/child-skill/SKILL.md" in reviewer
        assert "root-skill/SKILL.md\"\nenabled = false" in reviewer
        assert "child-skill/SKILL.md\"\nenabled = true" in reviewer
        child_root = deployment.root / "role-skills" / "reviewer"
        assert child_root in deployment.codex_skill_roots
        parent_settings = dict(deployment.codex_parent_skill_settings)
        assert parent_settings[
            (deployment.generated_skill_root / "root-skill" / "SKILL.md").resolve()
        ] is True
        assert parent_settings[
            (child_root / "child-skill" / "SKILL.md").resolve()
        ] is False
        assert 'agent_type=\"native-critic\"' in reviewer
        assert "NESTED_SECRET" not in reviewer
        assert "NESTED_SECRET" in critic
    finally:
        deployment.cleanup()


def test_codex_child_path_skill_is_discovered_but_disabled_for_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root_skill = tmp_path / "root-skills" / "root-skill"
    child_skill = tmp_path / "child-skills" / "child-skill"
    for path in (root_skill, child_skill):
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("---\nname: skill\n---\nUse it.\n")
    agent = Agent(
        instructions="parent",
        skills=(Skill.from_path(root_skill),),
        subagents={
            "reviewer": Agent(
                instructions="review",
                skills=(Skill.from_path(child_skill),),
            )
        },
    )
    deployment = deploy_runtime(agent, "codex", tmp_path / "runtime")
    adapter = CodexAppServer()
    process = Process()
    adapter._deployments[id(process)] = deployment
    calls: list[tuple[str, dict]] = []

    def capture(_process, method, params, _timeout):
        calls.append((method, params))
        return {}

    monkeypatch.setattr("yoke.providers.codex_app_server.request_rpc", capture)
    try:
        request = Harness(provider="codex", agent=agent, cwd=tmp_path / "workspace")
        adapter._configure_skill_roots(process, request)
        roots = calls[0][1]["extraRoots"]
        reviewer = Path(
            deployment.codex_agents["reviewer"]["config_file"]
        ).read_text()

        assert str(root_skill.parent.resolve()) in roots
        assert str(child_skill.parent.resolve()) in roots
        assert str(child_skill.resolve()) in reviewer
        assert f'path = "{child_skill.resolve()}"\nenabled = true' in reviewer
        config = codex_runtime_config(deployment)
        settings = {
            item["path"]: item["enabled"] for item in config["skills"]["config"]
        }
        assert settings[str(root_skill.resolve())] is True
        assert settings[str(child_skill.resolve())] is False
    finally:
        deployment.cleanup()


def test_codex_thread_uses_registered_role_without_prompt_secrets(
    tmp_path: Path,
) -> None:
    agent = agent_with_native_features("SUBAGENT_SECRET")
    agent = agent.model_copy(
        update={
            "subagents": {
                "reviewer": agent.subagents["reviewer"].model_copy(
                    update={"options": {"codex_name": "native-reviewer"}}
                )
            }
        }
    )
    harness = Harness(provider="codex", agent=agent, cwd=tmp_path)
    deployment = deploy_runtime(agent, "codex", tmp_path)
    try:
        params = thread_params(
            harness,
            Permissions(),
            None,
            False,
            deployment=deployment,
        )
        instructions = params["developerInstructions"]
        config = codex_runtime_config(deployment)

        assert 'agent_type="native-reviewer"' in instructions
        assert "SUBAGENT_SECRET" not in instructions
        assert "check sources" not in instructions
        assert config["agents"]["native-reviewer"]["config_file"].startswith(
            str(deployment.root)
        )
        assert config["features"]["multi_agent_v2"] == {
            "enabled": True,
            "hide_spawn_agent_metadata": False,
        }
    finally:
        deployment.cleanup()


def test_codex_skill_config_override_is_toml_sequence() -> None:
    overrides = config_overrides(
        {
            "skills": {
                "config": [
                    {"path": "/tmp/root/SKILL.md", "enabled": True},
                    {"path": "/tmp/child/SKILL.md", "enabled": False},
                ]
            }
        }
    )

    assert overrides == [
        "skills.config=[{ path = \"/tmp/root/SKILL.md\", enabled = true }, "
        "{ path = \"/tmp/child/SKILL.md\", enabled = false }]"
    ]
    value = overrides[0].split("=", 1)[1]
    assert tomllib.loads(f"value = {value}")["value"] == [
        {"path": "/tmp/root/SKILL.md", "enabled": True},
        {"path": "/tmp/child/SKILL.md", "enabled": False},
    ]


def test_codex_runtime_skill_policy_preserves_authored_entries_and_wins_conflicts(
) -> None:
    base = {
        "skills": {
            "config": [
                {"path": "/authored/only", "enabled": True},
                {"path": "/managed/child", "enabled": True},
            ],
            "other": "preserved",
        }
    }
    runtime = {
        "skills": {
            "config": [
                {"path": "/managed/root", "enabled": True},
                {"path": "/managed/child", "enabled": False},
            ]
        }
    }

    merged = merged_runtime_config(base, runtime)

    assert merged["skills"] == {
        "config": [
            {"path": "/authored/only", "enabled": True},
            {"path": "/managed/root", "enabled": True},
            {"path": "/managed/child", "enabled": False},
        ],
        "other": "preserved",
    }
    assert base["skills"]["config"][1]["enabled"] is True


class Process:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_codex_adapter_cleans_runtime_on_close(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = CodexAppServer()
        process = Process()
        captured: dict[str, object] = {}

        def start_process(cwd, environment=None, runtime_config=None):
            captured["config"] = runtime_config
            return process

        def start_thread(started, harness, options, permissions, goal):
            return AppServerThread(
                process=started,
                thread_id="thread-1",
                cwd=harness.cwd,
                permissions=permissions,
                effort=None,
                provider_options={},
            )

        adapter._start_process = start_process  # type: ignore[method-assign]
        adapter._start_thread = start_thread  # type: ignore[method-assign]
        runtime_root = tmp_path / "runtime"
        cwd = tmp_path / "workspace"
        harness = Harness(
            provider="codex",
            agent=agent_with_native_features(),
            cwd=cwd,
            runtime_root=runtime_root,
        )

        session = await adapter.start(harness, SessionOptions())
        assert session.runtime_root == runtime_root
        assert "runtime_root" not in session.model_dump()
        assert list(runtime_root.iterdir())
        assert captured["config"]
        await adapter.close(session)
        assert not list(runtime_root.iterdir())
        assert process.terminated

    asyncio.run(exercise())


def test_codex_adapter_cleans_runtime_when_start_fails(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = CodexAppServer()
        process = Process()
        adapter._start_process = (  # type: ignore[method-assign]
            lambda cwd, environment=None, runtime_config=None: process
        )
        adapter._start_thread = (  # type: ignore[method-assign]
            lambda *_args: (_ for _ in ()).throw(RuntimeError("start failed"))
        )
        runtime_root = tmp_path / "runtime"
        cwd = tmp_path / "workspace"
        harness = Harness(
            provider="codex",
            agent=agent_with_native_features(),
            cwd=cwd,
            runtime_root=runtime_root,
        )

        with pytest.raises(RuntimeError, match="start failed"):
            await adapter.start(harness, SessionOptions())
        assert not list(runtime_root.iterdir())
        assert process.terminated

    asyncio.run(exercise())


def test_codex_adapter_unwinds_when_goal_setup_fails(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = CodexAppServer()
        process = Process()
        adapter._start_process = (  # type: ignore[method-assign]
            lambda cwd, environment=None, runtime_config=None: process
        )
        adapter._start_thread = (  # type: ignore[method-assign]
            lambda started, harness, options, permissions, goal: AppServerThread(
                process=started,
                thread_id="thread-goal",
                cwd=harness.cwd,
                permissions=permissions,
                effort=None,
                provider_options={},
            )
        )

        async def fail_goal(session, goal):
            raise RuntimeError("goal failed")

        adapter.set_goal = fail_goal  # type: ignore[method-assign]
        runtime_root = tmp_path / "runtime"
        request = Harness(
            provider="codex",
            agent=agent_with_native_features(),
            cwd=tmp_path / "workspace",
            runtime_root=runtime_root,
        )
        with pytest.raises(RuntimeError, match="goal failed"):
            await adapter.start(
                request,
                SessionOptions(goal={"objective": "finish"}),
            )
        assert not adapter._threads
        assert not adapter._process_refs
        assert not adapter._deployments
        assert not list(runtime_root.iterdir())
        assert process.terminated

    asyncio.run(exercise())


def test_codex_shared_process_keeps_runtime_until_last_release(tmp_path: Path) -> None:
    adapter = CodexAppServer()
    process = Process()
    deployment = deploy_runtime(agent_with_native_features(), "codex", tmp_path)
    adapter._deployments[id(process)] = deployment
    adapter._retain_process(process)
    adapter._retain_process(process)

    adapter._release_process(process)
    assert deployment.root.exists()
    assert not process.terminated

    adapter._release_process(process)
    assert not deployment.root.exists()
    assert process.terminated


def test_codex_concurrent_sessions_have_isolated_runtimes(tmp_path: Path) -> None:
    async def exercise() -> None:
        adapter = CodexAppServer()
        counter = 0

        def start_process(cwd, environment=None, runtime_config=None):
            return Process()

        def start_thread(started, harness, options, permissions, goal):
            nonlocal counter
            counter += 1
            return AppServerThread(
                process=started,
                thread_id=f"thread-{counter}",
                cwd=harness.cwd,
                permissions=permissions,
                effort=None,
                provider_options={},
            )

        adapter._start_process = start_process  # type: ignore[method-assign]
        adapter._start_thread = start_thread  # type: ignore[method-assign]
        request = Harness(
            provider="codex",
            agent=agent_with_native_features(),
            cwd=tmp_path / "workspace",
            runtime_root=tmp_path / "runtime",
        )
        first = await adapter.start(request, SessionOptions())
        second = await adapter.start(request, SessionOptions())
        roots = [item.root for item in adapter._deployments.values()]
        assert len(set(roots)) == 2

        await adapter.close(first)
        assert sum(root.exists() for root in roots) == 1
        await adapter.close(second)
        assert not any(root.exists() for root in roots)

    asyncio.run(exercise())
