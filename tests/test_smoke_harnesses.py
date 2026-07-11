from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from yoke import (
    Agent,
    Channel,
    Event,
    Harness,
    Readiness,
    Run,
    RunStatus,
    Surface,
    Tool,
    ToolKind,
    WorkflowRun,
    WorkflowTrace,
)


def load_smoke_module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "smoke_harnesses.py"
    spec = importlib.util.spec_from_file_location("smoke_harnesses", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke_checks() -> tuple[Harness, ...]:
    agent = Agent(instructions="test")
    cwd = Path.cwd()
    return (
        Harness(provider="codex", surface="codex_cli", agent=agent, cwd=cwd),
        Harness(provider="codex", surface="codex_app_server", agent=agent, cwd=cwd),
        Harness(provider="claude", surface="claude_python_sdk", agent=agent, cwd=cwd),
    )


def all_smoke_checks() -> tuple[Harness, ...]:
    agent = Agent(instructions="test")
    cwd = Path.cwd()
    return (
        Harness(provider="codex", surface="codex_cli", agent=agent, cwd=cwd),
        Harness(provider="codex", surface="codex_app_server", agent=agent, cwd=cwd),
        Harness(provider="codex", surface="codex_python_sdk", agent=agent, cwd=cwd),
        Harness(provider="claude", surface="claude_python_sdk", agent=agent, cwd=cwd),
    )


def test_smoke_channel_filter_selects_exposure_paths() -> None:
    smoke = load_smoke_module()

    selected = smoke.filter_channels(smoke_checks(), ["app_server"])

    assert [harness.surface for harness in selected] == [Surface.CODEX_APP_SERVER]
    assert [harness.profile().channel for harness in selected] == [
        Channel.APP_SERVER
    ]


def test_smoke_channel_filter_intersects_with_surface_filter() -> None:
    smoke = load_smoke_module()
    exact = smoke.filter_checks(smoke_checks(), ["codex:app", "claude:sdk"])

    selected = smoke.filter_channels(exact, ["sdk"])

    assert [harness.surface for harness in selected] == [Surface.CLAUDE_PYTHON_SDK]


def test_smoke_channel_filter_reports_available_channels() -> None:
    smoke = load_smoke_module()
    exact = smoke.filter_checks(smoke_checks(), ["codex:app"])

    try:
        smoke.filter_channels(exact, ["sdk"])
    except SystemExit as error:
        message = str(error)
        assert "no smoke surfaces matched channel sdk" in message
        assert "available channels: app_server" in message
    else:
        raise AssertionError("expected SystemExit")


def test_smoke_feature_filter_selects_supporting_surfaces() -> None:
    smoke = load_smoke_module()

    selected = smoke.filter_features(smoke_checks(), ["readable_goal"])

    assert [harness.surface for harness in selected] == [Surface.CODEX_APP_SERVER]


def test_smoke_feature_filter_intersects_with_channel_filter() -> None:
    smoke = load_smoke_module()
    app_server = smoke.filter_channels(smoke_checks(), ["app_server"])

    selected = smoke.filter_features(app_server, ["readable_goal", "streaming"])

    assert [harness.surface for harness in selected] == [Surface.CODEX_APP_SERVER]


def test_smoke_feature_filter_reports_missing_features() -> None:
    smoke = load_smoke_module()
    sdk = smoke.filter_channels(smoke_checks(), ["sdk"])

    try:
        smoke.filter_features(sdk, ["readable_goal"])
    except SystemExit as error:
        message = str(error)
        assert "no smoke surfaces support features readable_goal" in message
        assert "claude:claude_python_sdk missing readable_goal" in message
    else:
        raise AssertionError("expected SystemExit")


def test_smoke_surface_filter_accepts_aliases() -> None:
    smoke = load_smoke_module()

    selected = smoke.filter_checks(smoke_checks(), ["codex:app", "claude:sdk"])

    assert [harness.surface for harness in selected] == [
        Surface.CODEX_APP_SERVER,
        Surface.CLAUDE_PYTHON_SDK,
    ]


def test_smoke_surface_filter_accepts_exact_names() -> None:
    smoke = load_smoke_module()

    selected = smoke.filter_checks(smoke_checks(), ["codex:codex_cli"])

    assert len(selected) == 1
    assert selected[0].surface is Surface.CODEX_CLI


def test_smoke_surface_filter_rejects_auto() -> None:
    smoke = load_smoke_module()

    try:
        smoke.filter_checks(smoke_checks(), ["codex:auto"])
    except SystemExit as error:
        assert "concrete surface" in str(error)
    else:
        raise AssertionError("expected SystemExit")


def test_smoke_surface_filter_reports_available_surfaces() -> None:
    smoke = load_smoke_module()

    try:
        smoke.filter_checks(smoke_checks(), ["codex:typescript"])
    except SystemExit as error:
        message = str(error)
        assert "unknown smoke surface codex:codex_typescript_sdk" in message
        assert "codex:codex_cli" in message
        assert "codex:codex_app_server" in message
    else:
        raise AssertionError("expected SystemExit")


def test_readiness_record_reports_exact_surface_names() -> None:
    smoke = load_smoke_module()
    harness = Harness(
        provider="codex",
        surface="app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    readiness = Readiness(
        provider="codex",
        surface=harness.surface,
        available=True,
        message="ready",
    )

    assert smoke.readiness_record(harness, readiness) == {
        "provider": "codex",
        "surface": "codex_app_server",
        "channel": "app_server",
        "available": True,
        "message": "ready",
        "fix": None,
    }


def test_readiness_record_can_include_capability_report() -> None:
    smoke = load_smoke_module()
    harness = Harness(
        provider="codex",
        surface="app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    readiness = Readiness(
        provider="codex",
        surface=harness.surface,
        available=True,
        message="ready",
    )

    record = smoke.readiness_record(
        harness,
        readiness,
        include_capabilities=True,
    )

    assert record["capabilities"]["provider"] == "codex"
    assert record["capabilities"]["surface"] == "codex_app_server"
    assert record["capabilities"]["channel"] == "app_server"
    assert "https://developers.openai.com/codex/app-server" in record[
        "capabilities"
    ]["evidence"]
    feature_rows = {
        feature["feature"]: feature
        for feature in record["capabilities"]["features"]
    }
    assert feature_rows["readable_goal"]["support"] == "native"
    assert feature_rows["readable_goal"]["lowering"] == (
        "Session.get_goal calls app-server thread/goal/get."
    )


def test_print_capabilities_shows_lowering_rows(capsys) -> None:
    smoke = load_smoke_module()
    harness = Harness(
        provider="codex",
        surface="app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    smoke.print_capabilities(harness)

    output = capsys.readouterr().out
    assert "capabilities: codex:codex_app_server [app_server]" in output
    assert "readable_goal: native" in output
    assert "lowering: Session.get_goal calls app-server thread/goal/get." in output
    assert "collabAgentToolCall" in output


def test_print_readiness_shows_channel(capsys) -> None:
    smoke = load_smoke_module()
    harness = Harness(
        provider="codex",
        surface="app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    readiness = Readiness(
        provider="codex",
        surface=harness.surface,
        available=True,
        message="ready",
    )

    smoke.print_readiness(harness, readiness)

    output = capsys.readouterr().out
    assert "codex:codex_app_server [app_server]: ok: ready" in output


def test_claude_hooks_smoke_uses_hook_options(monkeypatch) -> None:
    smoke = load_smoke_module()

    class FakeHookMatcher:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakePermissionResultAllow:
        pass

    fake_sdk = SimpleNamespace(
        HookMatcher=FakeHookMatcher,
        PermissionResultAllow=FakePermissionResultAllow,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)

    class FakeHarness:
        prompt = None
        options = None

        def run_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output="yoke-claude-hooks-smoke",
                events=(Event(kind="hook"), Event(kind="tool_use", tool=Tool())),
            )

    harness = FakeHarness()

    assert smoke.run_claude_hooks_smoke(harness) == 0
    assert "Read tool" in harness.prompt
    assert harness.options.provider.claude.include_hook_events is True
    hooks = harness.options.provider.claude.raw["hooks"]
    assert set(hooks) == {"PreToolUse", "PostToolUse"}
    assert isinstance(hooks["PreToolUse"][0], FakeHookMatcher)


def test_claude_subagent_smoke_declares_subagent_and_requires_agent_event() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        provider = "claude"
        surface = "claude_python_sdk"
        cwd = Path.cwd()
        created = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.agent = kwargs.get("agent")
            self.prompt = None
            self.options = None
            self.created.append(self)

        def run_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output="yoke-claude-subagent-smoke",
                events=(
                    Event(
                        kind="tool_use",
                        tool=Tool(kind=ToolKind.AGENT),
                    ),
                ),
            )

    smoke.Harness = FakeHarness
    harness = FakeHarness(provider="claude", surface="claude_python_sdk")

    assert smoke.run_claude_subagent_smoke(harness) == 0
    subagent_harness = FakeHarness.created[-1]
    assert "readme-reviewer" in subagent_harness.prompt
    assert subagent_harness.options.max_turns == 6
    assert subagent_harness.agent is not None
    assert "readme-reviewer" in subagent_harness.agent.subagents


def test_codex_app_collab_smoke_requires_agent_event_and_typed_options() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        provider = "codex"
        surface = "codex_app_server"
        cwd = Path.cwd()

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.prompt = None
            self.options = None

        def run_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output="yoke-codex-collab-subagent-smoke",
                events=(
                    Event(
                        kind="tool_result",
                        tool=Tool(kind=ToolKind.AGENT),
                    ),
                ),
            )

    harness = FakeHarness()

    assert smoke.run_codex_app_collab_smoke(harness) == 0
    assert harness.prompt is not None
    assert "Spawn one explorer subagent" in harness.prompt
    assert harness.options.inherit_goal is False
    assert harness.options.max_turns == 8
    codex = harness.options.provider.codex
    assert codex.experimental_api is True
    assert codex.collaboration.mode == "plan"
    assert codex.collaboration.settings.developer_instructions is None
    assert codex.collaboration.settings.model == "gpt-5.4-mini"
    assert codex.collaboration.settings.reasoning_effort == "medium"


def test_codex_app_skill_smoke_wires_folder_skill() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        provider = "codex"
        surface = "codex_app_server"
        cwd = Path.cwd()
        created = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.agent = kwargs.get("agent")
            self.created.append(self)

        def run_sync(self, prompt, options):
            assert "yoke-smoke-skill" in prompt
            assert options.max_turns == 6
            assert self.agent is not None
            assert len(self.agent.skills) == 1
            skill = self.agent.skills[0]
            assert skill.path is not None
            assert skill.path.name == "yoke-smoke-skill"
            skill_text = (skill.path / "SKILL.md").read_text()
            assert "yoke-codex-skill-smoke" in skill_text
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output="yoke-codex-skill-smoke",
            )

    smoke.Harness = FakeHarness
    harness = FakeHarness(provider="codex", surface="codex_app_server")

    assert smoke.run_skill_smoke(
        harness,
        marker="yoke-codex-skill-smoke",
        label="codex_app_server skills",
    ) == 0
    skill_harness = FakeHarness.created[-1]
    assert skill_harness.agent.skills[0].path.name == "yoke-smoke-skill"


def test_claude_skill_smoke_wires_folder_skill() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        provider = "claude"
        surface = "claude_python_sdk"
        cwd = Path.cwd()

        def __init__(self, **kwargs):
            self.agent = kwargs.get("agent")

        def run_sync(self, prompt, options):
            assert prompt.startswith("/yoke-smoke-plugin:yoke-smoke-skill")
            assert options.inherit_goal is False
            assert self.agent is not None
            assert len(self.agent.skills) == 1
            skill = self.agent.skills[0]
            assert skill.path is not None
            assert skill.path.parent.name == "skills"
            skill_text = (skill.path / "SKILL.md").read_text()
            assert "yoke-claude-skill-smoke" in skill_text
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output="yoke-claude-skill-smoke",
            )

    smoke.Harness = FakeHarness
    harness = FakeHarness(provider="claude", surface="claude_python_sdk")

    assert smoke.run_skill_smoke(
        harness,
        marker="yoke-claude-skill-smoke",
        label="claude_python_sdk skills",
    ) == 0


def test_workflow_program_smoke_loads_folder_and_reuses_store() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        provider = "codex"
        surface = "codex_app_server"
        cwd = Path.cwd()
        created = []
        calls = 0

        def __init__(self, **kwargs):
            self.agent = kwargs.get("agent")
            self.created.append(self)

        def workflow_sync(self, workflow, args=None, options=None):
            assert workflow == "smoke"
            assert args is None
            assert options.resume == "yoke-codex-workflow-smoke-run"
            assert options.run.inherit_goal is False
            assert options.run.max_turns == 2
            assert self.agent is not None
            assert self.agent.instructions == (
                "You coordinate a tiny Yoke Workflow smoke."
            )
            assert "worker" in self.agent.subagents
            loaded_workflow = self.agent.workflows["smoke"]
            assert loaded_workflow.program_path is not None
            assert loaded_workflow.program_path.name == "workflow.py"
            assert "main(ctx)" in loaded_workflow.program_path.read_text()
            assert loaded_workflow.args == {"marker": "yoke-codex-workflow-smoke"}
            cached = bool(options.memory.get(options.resume, "fake-key"))
            if not cached:
                options.memory.put(
                    options.resume,
                    "fake-key",
                    Run(
                        provider="codex",
                        surface="codex_app_server",
                        output="yoke-codex-workflow-smoke",
                    ),
                )
            self.calls += 1
            return WorkflowRun(
                workflow="smoke",
                run_id=options.resume,
                provider="codex",
                surface="codex_app_server",
                status=RunStatus.SUCCEEDED,
                output="yoke-codex-workflow-smoke",
                traces=(
                    WorkflowTrace(
                        kind="agent",
                        id=options.resume,
                        cached=cached,
                        output="yoke-codex-workflow-smoke",
                    ),
                ),
            )

    smoke.Harness = FakeHarness
    harness = FakeHarness(provider="codex", surface="codex_app_server")

    assert smoke.run_workflow_program_smoke(
        harness,
        marker="yoke-codex-workflow-smoke",
        label="codex_app_server workflow",
    ) == 0
    workflow_harness = FakeHarness.created[-1]
    assert workflow_harness.calls == 2


def test_codex_app_request_smoke_uses_request_handler() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        prompt = None
        options = None

        def run_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            handler = options.provider.codex.app_server.request_handler
            event = Event(
                kind="approval_request",
                tool=Tool(kind=ToolKind.SHELL),
            )
            response = handler(event, object())
            assert response.decision == "allow"
            marker_path = prompt.split("Path('", 1)[1].split("')", 1)[0]
            output_path = prompt.split("Path('", 2)[2].split("')", 1)[0]
            marker = Path(marker_path).read_text().strip()
            Path(output_path).write_text(marker)
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output=marker,
                events=(event,),
            )

    harness = FakeHarness()

    assert smoke.run_codex_app_request_smoke(harness) == 0
    assert ".yoke-request-smoke-" in harness.prompt
    assert ".yoke-request-output-" in harness.prompt
    assert "read_text().strip()" in harness.prompt
    assert "write_text(marker)" in harness.prompt
    assert harness.options.permissions.access == "read"
    assert harness.options.permissions.approval == "ask"
    assert callable(harness.options.provider.codex.app_server.request_handler)


def test_codex_app_rename_smoke_renames_and_closes_session() -> None:
    smoke = load_smoke_module()

    class FakeSession:
        id = "thread-1"

        def __init__(self) -> None:
            self.closed = False
            self.title = None

        def rename_sync(self, title):
            self.title = title
            return SimpleNamespace(title=title)

        def close_sync(self):
            self.closed = True

    class FakeHarness:
        options = None

        def __init__(self) -> None:
            self.session = FakeSession()

        def start_sync(self, options):
            self.options = options
            return self.session

    harness = FakeHarness()

    assert smoke.run_codex_app_rename_smoke(harness) == 0
    assert harness.options.inherit_goal is False
    assert harness.session.title == "Yoke smoke rename"
    assert harness.session.closed is True


def test_smoke_plan_records_include_safe_readiness_and_live_commands() -> None:
    smoke = load_smoke_module()

    records = smoke.smoke_plan_records(all_smoke_checks())

    readiness = [record for record in records if record["kind"] == "readiness"]
    live = [record for record in records if record["kind"] == "live"]
    commands = {record["command"] for record in records}
    assert len(readiness) == 4
    assert all(record["safety"] == "safe" for record in readiness)
    assert any(record["feature"] == "goal loop" for record in live)
    assert any(record["feature"] == "permissions" for record in live)
    assert (
        "python scripts/smoke_harnesses.py "
        "--surface codex:codex_python_sdk --run-codex-sdk-stream"
    ) in commands
    assert (
        "python scripts/smoke_harnesses.py "
        "--surface claude:claude_python_sdk --run-claude-permissions"
    ) in commands


def test_print_smoke_plan_groups_readiness_and_live_commands(capsys) -> None:
    smoke = load_smoke_module()
    records = smoke.smoke_plan_records(
        (
            Harness(
                provider="codex",
                surface="app",
                agent=Agent(instructions="x"),
                cwd=Path.cwd(),
            ),
        )
    )

    smoke.print_smoke_plan(records)

    output = capsys.readouterr().out
    assert "Smoke plan (provider calls are opt-in):" in output
    assert "Readiness:" in output
    assert "Live smokes:" in output
    assert "codex:codex_app_server goal loop" in output


def test_codex_sdk_stream_smoke_uses_generic_stream_runner() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        prompt = None
        options = None

        def stream_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            return (
                Event(kind="provider_session"),
                Event(kind="message", message="yoke-sdk-stream-smoke"),
                Event(kind="done"),
            )

    harness = FakeHarness()

    assert smoke.run_stream_smoke(
        harness,
        marker="yoke-sdk-stream-smoke",
        label="codex_python_sdk stream",
    ) == 0
    assert harness.prompt == "Reply with exactly: yoke-sdk-stream-smoke"
    assert harness.options.inherit_goal is False
    assert harness.options.max_turns == 1


def test_claude_permission_smoke_wires_can_use_tool_callback(monkeypatch) -> None:
    smoke = load_smoke_module()

    class FakeHookMatcher:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakePermissionResultAllow:
        pass

    fake_sdk = SimpleNamespace(
        HookMatcher=FakeHookMatcher,
        PermissionResultAllow=FakePermissionResultAllow,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)

    class FakeHarness:
        prompt = None
        options = None

        def run_sync(self, prompt, options):
            self.prompt = prompt
            self.options = options
            callback = options.provider.claude.can_use_tool
            assert callback is not None
            hooks = options.provider.claude.hooks
            assert isinstance(hooks["PreToolUse"][0], FakeHookMatcher)
            result = asyncio.run(
                callback("Read", {"file_path": "README.md"}, SimpleNamespace())
            )
            assert isinstance(result, FakePermissionResultAllow)
            marker_path = Path(prompt.rsplit(": ", 1)[1])
            return SimpleNamespace(
                ok=True,
                status="succeeded",
                output=marker_path.read_text(),
                events=(Event(kind="permission"),),
            )

    harness = FakeHarness()

    assert smoke.run_claude_permission_smoke(harness) == 0
    assert "Read tool" in harness.prompt
    assert harness.options.inherit_goal is False
    assert harness.options.max_turns == 4


def test_codex_sdk_stream_smoke_can_validate_transport_without_text() -> None:
    smoke = load_smoke_module()

    class FakeHarness:
        def stream_sync(self, prompt, options):
            return (
                Event(kind="stream_event", message="turn/started"),
                Event(kind="stream_event", message="turn/completed"),
            )

    assert smoke.run_stream_smoke(
        FakeHarness(),
        marker="yoke-sdk-stream-smoke",
        label="codex_python_sdk stream",
        completion="turn/completed",
        require_provider_session=False,
        require_text=False,
    ) == 0
