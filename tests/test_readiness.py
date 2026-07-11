from __future__ import annotations

import asyncio
from pathlib import Path

from yoke import (
    Agent,
    Channel,
    ControlMode,
    ExposureMode,
    Feature,
    GoalMode,
    Harness,
    PermissionMode,
    Readiness,
    SkillMode,
    Status,
    SubagentMode,
    WorkflowMode,
    clear_adapters,
    register,
    report_for,
)
from yoke.providers.codex import Codex


class FakeReadyAdapter:
    provider = "claude"
    surface = "fake-ready"
    capabilities = None

    async def check(self, harness):
        return Readiness(
            provider="claude",
            surface="fake-ready",
            available=True,
            message="fake ready",
        )

    async def run(self, harness, prompt, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def models(self, harness):  # pragma: no cover - unused
        raise NotImplementedError

    async def start(self, harness, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def send(self, session, turn, options):  # pragma: no cover - unused
        raise NotImplementedError

    async def stream(self, session, turn, options):  # pragma: no cover - unused
        if False:
            yield None

    async def get_goal(self, session):  # pragma: no cover - unused
        return None

    async def set_goal(self, session, goal):  # pragma: no cover - unused
        return session

    async def clear_goal(self, session):  # pragma: no cover - unused
        return session

    async def close(self, session):  # pragma: no cover - unused
        return None


class FakeCodexStatusAdapter(FakeReadyAdapter):
    provider = "codex"

    def __init__(self, surface: str) -> None:
        self.surface = surface

    async def check(self, harness):
        return Readiness(
            provider="codex",
            surface=self.surface,
            available=True,
            message=f"{self.surface} ready",
        )


def test_harness_check_delegates_to_selected_adapter() -> None:
    asyncio.run(run_harness_check_delegates())


async def run_harness_check_delegates() -> None:
    clear_adapters()
    register(FakeReadyAdapter())
    harness = Harness(
        provider="claude",
        surface="fake-ready",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    readiness = await harness.check()

    assert readiness.available is True
    assert readiness.message == "fake ready"


def test_harness_status_combines_readiness_and_report() -> None:
    asyncio.run(run_harness_status_check())


async def run_harness_status_check() -> None:
    clear_adapters()
    register(FakeReadyAdapter())
    harness = Harness(
        provider="claude",
        surface="fake-ready",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    status = await harness.status()

    assert isinstance(status, Status)
    assert status.available is True
    assert status.readiness.message == "fake ready"
    assert status.message == "fake ready"
    assert status.fix is None
    assert status.report.provider == "claude"
    assert status.report.surface == "fake-ready"
    assert status.provider == "claude"
    assert status.surface == "fake-ready"
    assert status.channel == "custom"
    assert not status.supports(Feature.READABLE_GOAL)
    assert status.support_for(Feature.READABLE_GOAL) == "unknown"
    assert status.goal.mode is GoalMode.UNKNOWN
    assert status.goal.auto_continues is False
    assert status.goal.loop == "unknown"
    assert status.workflow.mode is WorkflowMode.UNKNOWN
    assert status.workflow.background is False
    assert status.skills.mode is SkillMode.UNKNOWN
    assert status.skills.skills == "unknown"
    assert status.skills.plugins == "unknown"
    assert status.subagents.mode is SubagentMode.UNKNOWN
    assert status.subagents.collab == "unknown"
    assert status.control.mode is ControlMode.UNKNOWN
    assert status.control.login == "unknown"
    assert status.control.models == "unknown"
    assert status.control.interrupt == "unknown"
    assert status.control.fork == "unknown"
    assert status.control.experimental == "unknown"
    assert status.exposure.mode is ExposureMode.UNKNOWN
    assert status.exposure.stable is False
    assert status.exposure.experimental == "unknown"
    assert status.exposure.runtime_options is False
    assert status.permissions.mode is PermissionMode.UNKNOWN
    assert status.permissions.neutral is False
    assert status.history.list == "unknown"
    assert status.history.read == "unknown"
    assert status.history.compact == "unknown"
    assert status.history.rename == "unknown"
    assert status.history.tag == "unknown"


def test_status_goal_report_names_native_thread_goal_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.goal.mode is GoalMode.NATIVE_THREAD
    assert status.goal.run == "native"
    assert status.goal.mutable == "native"
    assert status.goal.readable == "native"
    assert status.goal.loop == "native"
    assert status.goal.auto_continues is True
    assert status.goal.note is not None
    assert "provider thread state" in status.goal.note
    assert "beyond one normal run" in status.goal.note


def test_status_goal_report_names_compiled_goal_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_python_sdk"),
    )

    assert status.goal.mode is GoalMode.COMPILED_CONTEXT
    assert status.goal.run == "compiled"
    assert status.goal.mutable == "unsupported"
    assert status.goal.readable == "unsupported"
    assert status.goal.loop == "unsupported"
    assert status.goal.auto_continues is False
    assert status.goal.note is not None
    assert "does not turn them into an automatic keep-working loop" in (
        status.goal.note
    )


def test_status_goal_report_names_provider_goal_loops() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_cli",
            available=True,
            message="tracked surface",
        ),
        report=report_for("claude", "claude_cli"),
    )

    assert status.goal.mode is GoalMode.PROVIDER_LOOP
    assert status.goal.run == "compiled"
    assert status.goal.mutable == "unsupported"
    assert status.goal.readable == "unsupported"
    assert status.goal.loop == "native"
    assert status.goal.auto_continues is True
    assert status.goal.note is not None
    assert "provider-owned goal loop" in status.goal.note
    assert "does not expose readable or mutable goal state" in status.goal.note


def test_status_workflow_report_names_portable_workflow_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.workflow.mode is WorkflowMode.YOKE_PORTABLE
    assert status.workflow.portable == "emulated"
    assert status.workflow.native == "unsupported"
    assert status.workflow.background is False
    assert status.workflow.script is False
    assert status.workflow.resumable is False
    assert status.workflow.max_concurrent_agents is None
    assert status.workflow.max_agents is None


def test_status_workflow_report_names_provider_native_workflow_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_typescript_sdk",
            available=False,
            message="tracked surface",
        ),
        report=report_for("claude", "claude_typescript_sdk"),
    )

    assert status.workflow.mode is WorkflowMode.PROVIDER_NATIVE
    assert status.workflow.portable == "native"
    assert status.workflow.native == "native"
    assert status.workflow.background is True
    assert status.workflow.script is True
    assert status.workflow.resumable is True
    assert status.workflow.max_concurrent_agents == 16
    assert status.workflow.max_agents == 1000


def test_status_subagent_report_names_provider_native_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.subagents.mode is SubagentMode.PROVIDER_NATIVE
    assert status.subagents.runtime == "codex_app_server"
    assert status.subagents.collab == "native"
    assert status.subagents.declared == "compiled"
    assert status.subagents.filesystem == "native"
    assert status.subagents.definition_sources == (
        ".codex/agents",
        "compiled_instructions",
    )
    assert status.subagents.built_in is False
    assert status.subagents.agent_tool is False
    assert status.subagents.events is True


def test_status_subagent_report_names_declared_provider_agents() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("claude", "claude_python_sdk"),
    )

    assert status.subagents.mode is SubagentMode.DECLARED
    assert status.subagents.inline == "native"
    assert status.subagents.declared == "native"
    assert status.subagents.collab == "unsupported"
    assert status.subagents.definition_sources == (
        "agents_parameter",
        ".claude/agents",
    )
    assert status.subagents.built_in is True
    assert status.subagents.agent_tool is True
    assert status.subagents.events is True


def test_status_subagent_report_names_compiled_subagents() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_python_sdk"),
    )

    assert status.subagents.mode is SubagentMode.COMPILED
    assert status.subagents.inline == "unsupported"
    assert status.subagents.declared == "compiled"
    assert status.subagents.collab == "unsupported"
    assert status.subagents.definition_sources == ("compiled_instructions",)
    assert status.subagents.built_in is False
    assert status.subagents.agent_tool is False
    assert status.subagents.events is False


def test_status_skill_report_names_provider_native_skill_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.skills.mode is SkillMode.PROVIDER_NATIVE
    assert status.skills.runtime == "codex_app_server"
    assert status.skills.skills == "native"
    assert status.skills.hooks == "native"
    assert status.skills.mcp == "native"


def test_status_skill_report_names_claude_sdk_skill_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("claude", "claude_python_sdk"),
    )

    assert status.skills.mode is SkillMode.PROVIDER_NATIVE
    assert status.skills.skills == "native"
    assert status.skills.hooks == "native"
    assert status.skills.mcp == "native"


def test_status_skill_report_names_compiled_skill_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_python_sdk"),
    )

    assert status.skills.mode is SkillMode.COMPILED
    assert status.skills.skills == "compiled"
    assert status.skills.hooks == "unsupported"
    assert status.skills.mcp == "compiled"


def test_status_control_report_names_programmatic_login_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_python_sdk"),
    )

    assert status.control.mode is ControlMode.PROGRAMMATIC
    assert status.control.runtime == "codex_app_server"
    assert status.control.login == "native"
    assert status.control.models == "native"
    assert status.control.interrupt == "native"
    assert status.control.fork == "native"
    assert status.control.request_events == "unsupported"
    assert status.control.request_callbacks == "unsupported"
    assert status.control.experimental == "unsupported"


def test_status_control_report_names_external_auth_live_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.control.mode is ControlMode.EXTERNAL_AUTH
    assert status.control.login == "unsupported"
    assert status.control.models == "native"
    assert status.control.interrupt == "native"
    assert status.control.fork == "native"
    assert status.control.request_events == "native"
    assert status.control.request_callbacks == "unsupported"
    assert status.control.experimental == "native"
    assert status.control.note is not None
    assert "authentication is handled outside Yoke" in status.control.note


def test_status_control_report_names_claude_sdk_external_auth() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("claude", "claude_python_sdk"),
    )

    assert status.control.mode is ControlMode.EXTERNAL_AUTH
    assert status.control.login == "unsupported"
    assert status.control.models == "unsupported"
    assert status.control.interrupt == "native"
    assert status.control.fork == "native"
    assert status.control.request_events == "unsupported"
    assert status.control.request_callbacks == "native"


def test_status_exposure_report_names_codex_app_server_protocol() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.exposure.mode is ExposureMode.PROTOCOL
    assert status.exposure.protocol == "codex_app_server_json_rpc"
    assert status.exposure.stable is True
    assert status.exposure.experimental == "native"
    assert status.exposure.runtime_options is True
    assert status.exposure.note is not None
    assert "JSON-RPC" in status.exposure.note


def test_status_exposure_report_names_sdk_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("claude", "claude_python_sdk"),
    )

    assert status.exposure.mode is ExposureMode.SDK
    assert status.exposure.protocol == "claude_sdk"
    assert status.exposure.stable is True
    assert status.exposure.experimental == "unsupported"
    assert status.exposure.runtime_options is True
    assert status.exposure.note is not None
    assert "callbacks" in status.exposure.note


def test_status_exposure_report_names_cli_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_cli",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_cli"),
    )

    assert status.exposure.mode is ExposureMode.CLI
    assert status.exposure.protocol == "process"
    assert status.exposure.stable is True
    assert status.exposure.experimental == "unsupported"
    assert status.exposure.runtime_options is False


def test_status_permission_report_names_codex_native_controls() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.permissions.mode is PermissionMode.CODEX_NATIVE
    assert status.permissions.neutral is True
    assert status.permissions.sandbox is True
    assert status.permissions.approval is True
    assert status.permissions.network is True
    assert status.permissions.approval_reviewer is True
    assert status.permissions.permission_mode is False


def test_status_permission_report_names_claude_sdk_controls() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_python_sdk",
            available=True,
            message="ready",
        ),
        report=report_for("claude", "claude_python_sdk"),
    )

    assert status.permissions.mode is PermissionMode.CLAUDE_NATIVE
    assert status.permissions.neutral is True
    assert status.permissions.permission_mode is True
    assert status.permissions.tool_rules is True
    assert status.permissions.hooks is True
    assert status.permissions.callbacks is True
    assert status.permissions.dynamic is True
    assert status.permissions.sandbox is False


def test_status_permission_report_names_external_claude_cli_controls() -> None:
    status = Status(
        readiness=Readiness(
            provider="claude",
            surface="claude_cli",
            available=True,
            message="tracked surface",
        ),
        report=report_for("claude", "claude_cli"),
    )

    assert status.permissions.mode is PermissionMode.EXTERNAL
    assert status.permissions.neutral is True
    assert status.permissions.permission_mode is False
    assert status.permissions.note is not None
    assert "outside Yoke" in status.permissions.note


def test_status_history_report_names_stored_session_surfaces() -> None:
    status = Status(
        readiness=Readiness(
            provider="codex",
            surface="codex_app_server",
            available=True,
            message="ready",
        ),
        report=report_for("codex", "codex_app_server"),
    )

    assert status.history.list == "native"
    assert status.history.read == "native"
    assert status.history.resume == "native"
    assert status.history.compact == "native"
    assert status.history.rename == "native"
    assert status.history.tag == "unsupported"


def test_harness_statuses_filter_by_channel() -> None:
    asyncio.run(run_harness_statuses_channel_check())


async def run_harness_statuses_channel_check() -> None:
    clear_adapters()
    register(FakeCodexStatusAdapter("codex_cli"))
    register(FakeCodexStatusAdapter("codex_python_sdk"))
    register(FakeCodexStatusAdapter("codex_app_server"))
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    statuses = await harness.statuses(channel=Channel.APP_SERVER)

    assert [status.surface for status in statuses] == ["codex_app_server"]
    assert statuses[0].available is True
    assert statuses[0].channel == "app_server"


def test_harness_statuses_sync_reports_runnable_surfaces() -> None:
    clear_adapters()
    register(FakeCodexStatusAdapter("codex_cli"))
    register(FakeCodexStatusAdapter("codex_python_sdk"))
    register(FakeCodexStatusAdapter("codex_app_server"))
    harness = Harness(
        provider="codex",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    statuses = harness.statuses_sync()

    assert [status.surface for status in statuses] == [
        "codex_cli",
        "codex_python_sdk",
        "codex_app_server",
    ]
    assert all(status.available for status in statuses)


def test_codex_check_reports_missing_executable() -> None:
    asyncio.run(run_missing_codex_check())


async def run_missing_codex_check() -> None:
    adapter = Codex(executable="yoke-missing-codex-for-test")
    harness = Harness(
        provider="codex",
        surface="codex_cli",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    readiness = await adapter.check(harness)

    assert readiness.available is False
    assert readiness.message == "codex not found on PATH"
    assert readiness.fix is not None
