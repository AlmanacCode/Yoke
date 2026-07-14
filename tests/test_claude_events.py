from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yoke import EventKind, ToolKind, ToolStatus
from yoke.providers.claude import ClaudeEventState, claude_events


@dataclass
class AssistantMessage:
    content: list[Any]
    message_id: str = "msg-1"
    session_id: str = "session-1"
    parent_tool_use_id: str | None = None
    usage: dict[str, Any] | None = None


@dataclass
class UserMessage:
    content: list[Any]
    uuid: str = "user-1"
    session_id: str = "session-1"
    parent_tool_use_id: str | None = None


@dataclass
class SystemMessage:
    subtype: str
    data: dict[str, Any]


@dataclass
class ResultMessage:
    result: str | None = None
    structured_output: Any | None = None
    usage: dict[str, Any] | None = None
    permission_denials: Any | None = None
    deferred_tool_use: Any | None = None
    errors: Any | None = None
    api_error_status: str | None = None
    uuid: str = "result-1"
    session_id: str = "session-1"
    subtype: str = "success"
    is_error: bool = False


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: Any
    is_error: bool = False


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str


@dataclass
class ServerToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ServerToolResultBlock:
    tool_use_id: str
    content: Any


@dataclass
class DeferredToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class TaskStartedMessage:
    task_id: str
    description: str
    uuid: str = "event-1"
    session_id: str = "session-1"
    tool_use_id: str | None = "toolu-parent"
    task_type: str | None = None


@dataclass
class TaskProgressMessage:
    task_id: str
    description: str
    usage: dict[str, Any]
    uuid: str = "event-2"
    session_id: str = "session-1"
    tool_use_id: str | None = "toolu-parent"
    last_tool_name: str | None = None


@dataclass
class TaskNotificationMessage:
    task_id: str
    status: str
    output_file: str
    summary: str
    uuid: str = "event-3"
    session_id: str = "session-1"
    tool_use_id: str | None = "toolu-parent"
    usage: dict[str, Any] | None = None


@dataclass
class TaskUpdatedMessage:
    task_id: str
    patch: dict[str, Any]
    status: str | None = None
    uuid: str | None = "event-4"
    session_id: str | None = "session-1"


@dataclass
class HookEventMessage:
    hook_event_name: str
    input: dict[str, Any]
    uuid: str = "hook-1"


@dataclass
class StreamEvent:
    event: dict[str, Any]
    uuid: str = "stream-1"
    session_id: str = "session-1"
    parent_tool_use_id: str | None = "toolu-parent"


def test_claude_tool_use_block_maps_to_tool_event() -> None:
    message = AssistantMessage(
        content=[
            ToolUseBlock(
                id="toolu-1",
                name="Bash",
                input={"command": "pytest", "cwd": "/repo"},
            )
        ]
    )

    events = claude_events(message)

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TOOL_USE
    assert event.message == "Bash: pytest"
    assert event.tool_id == "toolu-1"
    assert event.tool_name == "Bash"
    assert event.tool_input == '{"command": "pytest", "cwd": "/repo"}'
    assert event.provider_session_id == "session-1"
    assert event.provider_event_id == "msg-1"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.command == "pytest"
    assert event.tool.cwd == "/repo"
    assert event.tool.status is ToolStatus.STARTED


def test_claude_stream_text_delta_maps_to_text_delta_event() -> None:
    message = StreamEvent(
        event={
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "hello"},
        }
    )

    events = claude_events(message)

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TEXT_DELTA
    assert event.message == "hello"
    assert event.provider_session_id == "session-1"
    assert event.provider_event_id == "stream-1"
    assert event.provider_parent_tool_use_id == "toolu-parent"


def test_claude_only_init_system_message_creates_provider_session() -> None:
    initialized = claude_events(
        SystemMessage(subtype="init", data={"session_id": "session-1"})
    )[0]
    status = claude_events(
        SystemMessage(subtype="status", data={"session_id": "session-1"})
    )[0]

    assert initialized.kind is EventKind.PROVIDER_SESSION
    assert initialized.provider_session_id == "session-1"
    assert status.kind is EventKind.STREAM_EVENT
    assert status.provider_session_id == "session-1"


def test_claude_non_text_delta_remains_generic_stream_event() -> None:
    message = StreamEvent(
        event={
            "type": "content_block_delta",
            "delta": {"type": "thinking_delta", "text": "not assistant text"},
        }
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.STREAM_EVENT


def test_claude_tool_result_block_maps_to_tool_result_event() -> None:
    message = AssistantMessage(
        content=[
            ToolResultBlock(
                tool_use_id="toolu-1",
                content=[{"type": "text", "text": "3 passed"}],
            )
        ]
    )

    events = claude_events(message)

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TOOL_RESULT
    assert event.message == "tool completed"
    assert event.tool_id == "toolu-1"
    assert event.tool_result == [{"type": "text", "text": "3 passed"}]
    assert event.tool_is_error is False
    assert event.tool is not None
    assert event.tool.status is ToolStatus.COMPLETED


def test_claude_failed_tool_result_marks_failed_status() -> None:
    message = AssistantMessage(
        content=[
            ToolResultBlock(
                tool_use_id="toolu-1",
                content="permission denied",
                is_error=True,
            )
        ]
    )

    event = claude_events(message)[0]

    assert event.message == "permission denied"
    assert event.tool_is_error is True
    assert event.tool is not None
    assert event.tool.status is ToolStatus.FAILED


def test_claude_thinking_block_maps_to_summary_without_text_leak() -> None:
    message = AssistantMessage(
        content=[
            ThinkingBlock(
                thinking="private-ish provider thinking",
                signature="sig",
            )
        ]
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "thinking"
    assert event.tool_name == "thinking"
    assert event.tool_result == {
        "signature": "sig",
        "has_thinking": True,
    }
    assert "private-ish" not in str(event.message)


def test_claude_server_tool_use_maps_to_tool_event() -> None:
    message = AssistantMessage(
        content=[
            ServerToolUseBlock(
                id="srv-1",
                name="web_search",
                input={"query": "Yoke"},
            )
        ]
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_USE
    assert event.message == "web_search: Yoke"
    assert event.tool_id == "srv-1"
    assert event.tool_name == "web_search"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.WEB
    assert event.tool.status is ToolStatus.STARTED


def test_claude_server_tool_result_maps_to_tool_result() -> None:
    message = AssistantMessage(
        content=[
            ServerToolResultBlock(
                tool_use_id="srv-1",
                content={"status": "ok"},
            )
        ]
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_RESULT
    assert event.tool_id == "srv-1"
    assert event.tool_result == {"status": "ok"}
    assert event.tool_is_error is None
    assert event.tool is not None
    assert event.tool.status is ToolStatus.COMPLETED


def test_claude_assistant_usage_maps_to_context_usage_event() -> None:
    message = AssistantMessage(
        content=[],
        usage={
            "input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "cache_read_input_tokens": 4,
            "output_tokens": 6,
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.CONTEXT_USAGE
    assert event.message == "25 tokens"
    assert event.usage is not None
    assert event.usage.input_tokens == 10
    assert event.usage.cache_creation_input_tokens == 5
    assert event.usage.cached_input_tokens == 4
    assert event.usage.output_tokens == 6
    assert event.usage.total_tokens == 25
    assert event.usage.total_processed_tokens is None


def test_claude_result_usage_maps_to_context_usage_event_before_done() -> None:
    message = ResultMessage(
        result="ok",
        usage={"input_tokens": 1, "output_tokens": 2},
    )

    events = claude_events(message)

    assert events[0].kind is EventKind.TEXT
    assert events[0].message == "ok"
    assert events[1].kind is EventKind.CONTEXT_USAGE
    assert events[1].usage is not None
    assert events[1].usage.total_tokens == 3
    assert events[1].usage.total_processed_tokens == 3
    assert events[2].kind is EventKind.DONE


def test_claude_result_usage_includes_cache_creation_tokens() -> None:
    message = ResultMessage(
        usage={
            "input_tokens": 3,
            "cache_creation_input_tokens": 20_588,
            "cache_read_input_tokens": 0,
            "output_tokens": 5,
        },
    )

    usage_event = next(
        event
        for event in claude_events(message)
        if event.kind is EventKind.CONTEXT_USAGE
    )

    assert usage_event.usage is not None
    assert usage_event.usage.input_tokens == 3
    assert usage_event.usage.cache_creation_input_tokens == 20_588
    assert usage_event.usage.cached_input_tokens == 0
    assert usage_event.usage.output_tokens == 5
    assert usage_event.usage.total_tokens == 20_596
    assert usage_event.usage.total_processed_tokens == 20_596


def test_claude_result_errors_map_to_error_event_before_done() -> None:
    events = claude_events(
        ResultMessage(
            errors=[{"message": "provider failed"}],
            api_error_status="500",
        )
    )

    assert events[0].kind is EventKind.ERROR
    assert events[0].message == "provider failed"
    assert events[0].tool_is_error is True
    assert events[0].tool_result == {
        "errors": [{"message": "provider failed"}],
        "api_error_status": "500",
    }
    assert events[-1].kind is EventKind.DONE


def test_claude_result_deferred_tool_use_maps_to_tool_request() -> None:
    events = claude_events(
        ResultMessage(
            deferred_tool_use=DeferredToolUse(
                id="toolu-1",
                name="Bash",
                input={"command": "pytest"},
            )
        )
    )

    event = events[0]
    assert event.kind is EventKind.TOOL_REQUEST
    assert event.message == "deferred tool use: Bash"
    assert event.tool_id == "toolu-1"
    assert event.tool_name == "Bash"
    assert event.tool_input == '{"command": "pytest"}'
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.status is ToolStatus.STARTED
    assert event.tool_result == {
        "deferred": True,
        "input": {"command": "pytest"},
    }


def test_claude_result_permission_denials_map_to_warning() -> None:
    events = claude_events(ResultMessage(permission_denials=[{"tool": "Bash"}]))

    event = events[0]
    assert event.kind is EventKind.WARNING
    assert event.message == "Claude reported permission denials"
    assert event.tool_result == {"permission_denials": [{"tool": "Bash"}]}


def test_claude_empty_assistant_message_uses_stream_event_fallback() -> None:
    message = AssistantMessage(content=[])

    event = claude_events(message)[0]

    assert event.kind is EventKind.STREAM_EVENT
    assert event.raw is message


def test_claude_tool_kind_maps_file_and_agent_tools() -> None:
    message = AssistantMessage(
        content=[
            ToolUseBlock(id="read-1", name="Read", input={"file_path": "README.md"}),
            ToolUseBlock(id="agent-1", name="Agent", input={"prompt": "review"}),
            ToolUseBlock(id="mcp-1", name="mcp__github__search", input={}),
        ],
        parent_tool_use_id="parent-tool",
    )

    events = claude_events(message)

    assert events[0].tool is not None
    assert events[0].tool.kind is ToolKind.READ
    assert events[0].tool.path == "README.md"
    assert events[1].tool is not None
    assert events[1].tool.kind is ToolKind.AGENT
    assert events[2].tool is not None
    assert events[2].tool.kind is ToolKind.MCP
    assert all(event.provider_parent_tool_use_id == "parent-tool" for event in events)


def test_claude_agent_tool_use_and_result_share_lifecycle_metadata() -> None:
    state = ClaudeEventState()
    started = claude_events(
        AssistantMessage(
            content=[
                ToolUseBlock(
                    id="agent-1",
                    name="Agent",
                    input={
                        "prompt": "Review the diff",
                        "subagent_type": "reviewer",
                        "model": "claude-opus-4-1",
                        "reasoning_effort": "high",
                    },
                )
            ]
        ),
        state,
    )[0]
    completed = claude_events(
        UserMessage(
            content=[ToolResultBlock(tool_use_id="agent-1", content="Looks good")]
        ),
        state,
    )[0]

    assert started.agent is not None
    assert started.agent.action == "started"
    assert started.agent.agent_id == "agent-1"
    assert started.agent.agent_type == "reviewer"
    assert started.agent.prompt == "Review the diff"
    assert started.agent.model == "claude-opus-4-1"
    assert started.agent.reasoning_effort == "high"
    assert completed.kind is EventKind.TOOL_RESULT
    assert completed.agent is not None
    assert completed.agent.action == "completed"
    assert completed.agent.agent_id == "agent-1"
    assert completed.agent.states == {"status": "completed"}


def test_claude_non_agent_tool_result_does_not_gain_agent_metadata() -> None:
    state = ClaudeEventState()
    claude_events(
        AssistantMessage(
            content=[ToolUseBlock(id="read-1", name="Read", input={"path": "x"})]
        ),
        state,
    )

    result = claude_events(
        UserMessage(
            content=[ToolResultBlock(tool_use_id="read-1", content="contents")]
        ),
        state,
    )[0]

    assert result.agent is None


def test_claude_failed_agent_tool_result_marks_failed_lifecycle() -> None:
    state = ClaudeEventState()
    claude_events(
        AssistantMessage(
            content=[
                ToolUseBlock(
                    id="agent-1",
                    name="Task",
                    input={"prompt": "Review the diff"},
                )
            ]
        ),
        state,
    )

    failed = claude_events(
        UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="agent-1",
                    content="Subagent failed",
                    is_error=True,
                )
            ]
        ),
        state,
    )[0]

    assert failed.agent is not None
    assert failed.agent.action == "failed"
    assert failed.agent.agent_id == "agent-1"
    assert failed.agent.states == {"status": "failed"}


def test_claude_task_started_maps_agent_background_event() -> None:
    message = TaskStartedMessage(
        task_id="task-1",
        description="Review the diff",
        task_type="local_agent",
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_USE
    assert event.message == "Review the diff"
    assert event.tool_id == "task-1"
    assert event.tool_name == "local_agent"
    assert event.provider_session_id == "session-1"
    assert event.provider_event_id == "event-1"
    assert event.provider_parent_tool_use_id == "toolu-parent"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.AGENT
    assert event.tool.status is ToolStatus.STARTED
    assert event.agent is not None
    assert event.agent.action == "started"
    assert event.agent.agent_id == "task-1"
    assert event.agent.agent_type == "local_agent"
    assert event.agent.prompt == "Review the diff"


def test_claude_agent_task_result_preserves_correlated_completion() -> None:
    state = ClaudeEventState()
    claude_events(
        TaskStartedMessage(
            task_id="task-1",
            description="Review the diff",
            task_type="local_agent",
        ),
        state,
    )

    completed = claude_events(
        TaskNotificationMessage(
            task_id="task-1",
            status="completed",
            output_file="/tmp/task.md",
            summary="Found one issue",
        ),
        state,
    )[0]

    assert completed.agent is not None
    assert completed.agent.action == "completed"
    assert completed.agent.agent_id == "task-1"
    assert completed.agent.agent_type == "local_agent"
    assert completed.agent.states == {
        "status": "completed",
        "output_file": "/tmp/task.md",
    }


def test_claude_task_progress_maps_usage_and_last_tool() -> None:
    message = TaskProgressMessage(
        task_id="task-1",
        description="Searching files",
        usage={"total_tokens": 1234, "duration_ms": 250},
        last_tool_name="Grep",
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "Searching files"
    assert event.tool_id == "task-1"
    assert event.tool_name == "Grep"
    assert event.usage is not None
    assert event.usage.total_tokens == 1234
    assert event.usage.total_processed_tokens == 1234
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SEARCH
    assert event.tool.duration_ms == 250
    assert event.tool.summary == "Searching files"


def test_claude_task_notification_maps_completion_result() -> None:
    message = TaskNotificationMessage(
        task_id="task-1",
        status="completed",
        output_file="/tmp/task.md",
        summary="Found one issue",
        usage={"totalTokens": 2000, "durationMs": 500},
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_RESULT
    assert event.message == "Found one issue"
    assert event.tool_id == "task-1"
    assert event.tool_result == {
        "status": "completed",
        "output_file": "/tmp/task.md",
        "summary": "Found one issue",
    }
    assert event.tool_is_error is False
    assert event.usage is not None
    assert event.usage.total_tokens == 2000
    assert event.tool is not None
    assert event.tool.status is ToolStatus.COMPLETED
    assert event.tool.path == "/tmp/task.md"
    assert event.tool.duration_ms == 500


def test_claude_task_notification_maps_failed_and_stopped_status() -> None:
    failed = claude_events(
        TaskNotificationMessage(
            task_id="task-1",
            status="failed",
            output_file="/tmp/task.md",
            summary="Subagent failed",
        )
    )[0]
    stopped = claude_events(
        TaskNotificationMessage(
            task_id="task-2",
            status="stopped",
            output_file="/tmp/task.md",
            summary="Subagent stopped",
        )
    )[0]

    assert failed.tool is not None
    assert failed.tool.status is ToolStatus.FAILED
    assert failed.tool_is_error is True
    assert stopped.tool is not None
    assert stopped.tool.status is ToolStatus.DECLINED
    assert stopped.tool_is_error is False


def test_claude_task_updated_maps_running_patch_to_summary() -> None:
    message = TaskUpdatedMessage(
        task_id="task-1",
        patch={"status": "running", "progress": "reading"},
        status="running",
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "background task updated: running"
    assert event.tool_id == "task-1"
    assert event.tool_result == {
        "status": "running",
        "patch": {"status": "running", "progress": "reading"},
    }
    assert event.tool_is_error is False
    assert event.tool is not None
    assert event.tool.status is ToolStatus.STARTED
    assert event.provider_session_id == "session-1"
    assert event.provider_event_id == "event-4"


def test_claude_task_updated_maps_killed_patch_to_terminal_result() -> None:
    message = TaskUpdatedMessage(
        task_id="task-1",
        patch={"status": "killed"},
        status="killed",
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.TOOL_RESULT
    assert event.message == "background task finished: killed"
    assert event.tool is not None
    assert event.tool.status is ToolStatus.DECLINED
    assert event.tool_is_error is False


def test_claude_subagent_start_hook_carries_agent_identity() -> None:
    message = HookEventMessage(
        hook_event_name="SubagentStart",
        input={
            "session_id": "session-1",
            "agent_id": "agent-123",
            "agent_type": "reviewer",
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "SubagentStart: reviewer"
    assert event.provider_session_id == "session-1"
    assert event.provider_event_id == "hook-1"
    assert event.agent is not None
    assert event.agent.action == "started"
    assert event.agent.agent_id == "agent-123"
    assert event.agent.agent_type == "reviewer"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.AGENT
    assert event.tool.title == "reviewer"
    assert event.tool.status is ToolStatus.STARTED


def test_claude_subagent_stop_hook_carries_transcript_path() -> None:
    message = HookEventMessage(
        hook_event_name="SubagentStop",
        input={
            "session_id": "session-1",
            "agent_id": "agent-123",
            "agent_type": "reviewer",
            "agent_transcript_path": "/tmp/subagent.jsonl",
            "stop_hook_active": False,
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "SubagentStop: reviewer"
    assert event.agent is not None
    assert event.agent.action == "stopped"
    assert event.agent.agent_id == "agent-123"
    assert event.agent.agent_type == "reviewer"
    assert event.agent.states == {
        "agent_transcript_path": "/tmp/subagent.jsonl",
        "stop_hook_active": False,
    }
    assert event.tool is not None
    assert event.tool.kind is ToolKind.AGENT
    assert event.tool.path == "/tmp/subagent.jsonl"
    assert event.tool.status is ToolStatus.COMPLETED


def test_claude_non_subagent_tool_hook_stays_hook_with_tool_metadata() -> None:
    message = HookEventMessage(
        hook_event_name="PreToolUse",
        input={
            "session_id": "session-1",
            "tool_name": "Bash",
            "tool_use_id": "toolu-1",
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "PreToolUse: Bash"
    assert event.provider_session_id == "session-1"
    assert event.tool_id == "toolu-1"
    assert event.tool_name == "Bash"
    assert event.agent is None
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.status is ToolStatus.STARTED


def test_claude_pre_tool_hook_inside_subagent_carries_identity() -> None:
    message = HookEventMessage(
        hook_event_name="PreToolUse",
        input={
            "session_id": "session-1",
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "tool_use_id": "toolu-1",
            "agent_id": "agent-123",
            "agent_type": "reviewer",
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "PreToolUse: reviewer.Read"
    assert event.tool_id == "toolu-1"
    assert event.tool_name == "Read"
    assert event.tool_input == '{"file_path": "README.md"}'
    assert event.agent is not None
    assert event.agent.action == "tool_starting"
    assert event.agent.agent_id == "agent-123"
    assert event.agent.agent_type == "reviewer"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.READ
    assert event.tool.path == "README.md"
    assert event.tool.status is ToolStatus.STARTED


def test_claude_post_tool_hook_carries_response() -> None:
    message = HookEventMessage(
        hook_event_name="PostToolUse",
        input={
            "session_id": "session-1",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": {"stdout": "3 passed"},
            "tool_use_id": "toolu-1",
            "agent_id": "agent-123",
            "agent_type": "reviewer",
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "PostToolUse: reviewer.Bash"
    assert event.tool_result == {"stdout": "3 passed"}
    assert event.tool_is_error is False
    assert event.agent is not None
    assert event.agent.action == "tool_completed"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.command == "pytest"
    assert event.tool.status is ToolStatus.COMPLETED


def test_claude_post_tool_failure_hook_carries_error() -> None:
    message = HookEventMessage(
        hook_event_name="PostToolUseFailure",
        input={
            "session_id": "session-1",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "tool_use_id": "toolu-1",
            "error": "blocked",
            "agent_id": "agent-123",
            "agent_type": "reviewer",
        },
    )

    event = claude_events(message)[0]

    assert event.kind is EventKind.HOOK
    assert event.message == "PostToolUseFailure: reviewer.Bash"
    assert event.tool_result == "blocked"
    assert event.tool_is_error is True
    assert event.agent is not None
    assert event.agent.action == "tool_failed"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.status is ToolStatus.FAILED
    assert event.tool.summary == "blocked"
