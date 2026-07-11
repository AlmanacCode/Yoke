from __future__ import annotations

from pathlib import Path

import yoke


def test_public_api_exports_yoke_exceptions() -> None:
    assert issubclass(yoke.AdapterNotFound, yoke.YokeError)
    assert issubclass(yoke.UnsupportedFeature, yoke.YokeError)
    assert "YokeError" in yoke.__all__
    assert "UnsupportedFeature" in yoke.__all__
    assert "AdapterNotFound" in yoke.__all__
    assert "RuntimeOption" in yoke.__all__
    assert "runtime_options" in yoke.__all__
    assert "Collection" in yoke.__all__
    assert "RunRecord" in yoke.__all__
    assert "RunStore" in yoke.__all__
    assert "ControlMode" in yoke.__all__
    assert "ControlReport" in yoke.__all__
    assert "ClaudePermissionMode" in yoke.__all__
    assert "ClaudeToolset" in yoke.__all__
    assert "ClaudeToolsPreset" in yoke.__all__
    assert "CodexApproval" in yoke.__all__
    assert "CodexReviewer" in yoke.__all__
    assert "CodexSandbox" in yoke.__all__
    assert "GoalRun" in yoke.__all__
    assert "WorkflowMode" in yoke.__all__
    assert "WorkflowReport" in yoke.__all__
    assert "HistoryReport" in yoke.__all__
    assert "Hook" in yoke.__all__
    assert "HookEvent" in yoke.__all__
    assert "PermissionMode" in yoke.__all__
    assert "PermissionReport" in yoke.__all__
    assert "SkillMode" in yoke.__all__
    assert "SkillReport" in yoke.__all__
    assert "SubagentMode" in yoke.__all__
    assert "SubagentReport" in yoke.__all__
    assert "SurfaceFeature" in yoke.__all__
    assert "runtime_for" in yoke.__all__
    assert "SessionHistory" in yoke.__all__
    assert "SessionList" in yoke.__all__
    assert "SessionMessage" in yoke.__all__
    assert "SessionSummary" in yoke.__all__


def test_package_declares_typing_marker() -> None:
    assert (Path(yoke.__file__).parent / "py.typed").exists()
