from __future__ import annotations

from yoke.models import EventKind, ToolKind, ToolStatus
from yoke.providers.opencode.parts import (
    final_text_from_parts,
    infer_opencode_tool_kind,
    is_task_spawn,
    map_opencode_part,
)


def test_text_part_maps_to_text_event() -> None:
    events = map_opencode_part({"type": "text", "text": "hello"}, "session-1")

    assert len(events) == 1
    assert events[0].kind == EventKind.TEXT
    assert events[0].message == "hello"


def test_empty_text_part_maps_to_no_events() -> None:
    assert map_opencode_part({"type": "text"}, "session-1") == ()


def test_reasoning_part_maps_to_tool_summary() -> None:
    events = map_opencode_part({"type": "reasoning", "text": "thinking"}, "session-1")

    assert len(events) == 1
    assert events[0].kind == EventKind.TOOL_SUMMARY


def test_tool_part_maps_to_use_and_result_events() -> None:
    part = {
        "type": "tool",
        "tool": "read",
        "callID": "call-1",
        "state": {
            "status": "completed",
            "input": {"filePath": "src/foo.py"},
            "output": "contents",
        },
    }

    events = map_opencode_part(part, "session-1")

    assert len(events) == 2
    use_event, result_event = events
    assert use_event.kind == EventKind.TOOL_USE
    assert use_event.tool.kind == ToolKind.READ
    assert use_event.tool.path == "src/foo.py"
    assert use_event.source_thread_id == "session-1"
    assert result_event.kind == EventKind.TOOL_RESULT
    assert result_event.tool_result == "contents"
    assert result_event.tool_is_error is False


def test_failed_tool_part_marks_result_as_error() -> None:
    part = {
        "type": "tool",
        "tool": "bash",
        "state": {"status": "error", "input": {}, "output": "boom"},
    }

    _, result_event = map_opencode_part(part, "session-1")

    assert result_event.tool.status == ToolStatus.FAILED
    assert result_event.tool_is_error is True


def test_task_tool_part_carries_agent_call() -> None:
    part = {
        "type": "tool",
        "tool": "task",
        "state": {
            "status": "completed",
            "input": {"prompt": "do the thing"},
            "metadata": {"sessionId": "child-1"},
        },
    }

    use_event, result_event = map_opencode_part(part, "parent-1")

    assert use_event.agent is not None
    assert use_event.agent.new_thread_id == "child-1"
    assert use_event.agent.sender_thread_id == "parent-1"
    assert use_event.agent.prompt == "do the thing"
    assert use_event.agent.action == "completed"
    assert result_event.agent == use_event.agent


def test_non_task_tool_part_has_no_agent_call() -> None:
    part = {"type": "tool", "tool": "read", "state": {"status": "completed"}}

    use_event, _ = map_opencode_part(part, "session-1")

    assert use_event.agent is None


def test_patch_part_maps_to_files_changed_summary() -> None:
    events = map_opencode_part({"type": "patch", "files": ["a.py", "b.py"]}, "s")

    assert len(events) == 1
    assert "a.py" in events[0].message
    assert "b.py" in events[0].message


def test_empty_patch_part_maps_to_no_events() -> None:
    assert map_opencode_part({"type": "patch", "files": []}, "s") == ()


def test_step_finish_part_maps_to_context_usage() -> None:
    part = {"type": "step-finish", "tokens": {"input": 10, "output": 20, "total": 30}}

    events = map_opencode_part(part, "s")

    assert len(events) == 1
    assert events[0].kind == EventKind.CONTEXT_USAGE
    assert events[0].usage.total_tokens == 30


def test_unknown_part_type_maps_to_no_events() -> None:
    assert map_opencode_part({"type": "unknown-thing"}, "s") == ()


def test_infer_tool_kind_matches_common_tool_names() -> None:
    assert infer_opencode_tool_kind("read") == ToolKind.READ
    assert infer_opencode_tool_kind("bash") == ToolKind.SHELL
    assert infer_opencode_tool_kind("glob") == ToolKind.SEARCH
    assert infer_opencode_tool_kind("webfetch") == ToolKind.WEB
    assert infer_opencode_tool_kind("task") == ToolKind.AGENT
    assert infer_opencode_tool_kind("mystery") == ToolKind.UNKNOWN


def test_final_text_from_parts_returns_last_text_part() -> None:
    parts = [
        {"type": "text", "text": "first"},
        {"type": "tool", "tool": "read"},
        {"type": "text", "text": "last"},
    ]

    assert final_text_from_parts(parts) == "last"


def test_final_text_from_parts_returns_none_when_no_text() -> None:
    assert final_text_from_parts([{"type": "tool", "tool": "read"}]) is None


def test_is_task_spawn_detects_task_tool_with_session_id() -> None:
    part = {
        "type": "tool",
        "tool": "task",
        "state": {
            "input": {"description": "spawn a helper"},
            "metadata": {"sessionId": "child-9"},
        },
    }

    result = is_task_spawn(part)

    assert result == ("child-9", "spawn a helper")


def test_is_task_spawn_returns_none_for_non_task_tool() -> None:
    part = {"type": "tool", "tool": "read", "state": {}}

    assert is_task_spawn(part) is None
