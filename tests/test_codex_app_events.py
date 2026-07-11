from __future__ import annotations

import pytest

from yoke import (
    EventKind,
    GoalStatus,
    RequestPolicy,
    RunStatus,
    ToolKind,
    ToolStatus,
)
from yoke.providers.codex_app.events import TurnResult, map_notification, read_turn_step
from yoke.providers.codex_app.rpc import ServerResponse


@pytest.mark.parametrize("item_type", ["agentMessage", "reasoning", "userMessage"])
def test_internal_item_started_is_not_reported_as_a_tool(item_type: str) -> None:
    events = map_notification(
        {
            "method": "item/started",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {"id": "item-1", "type": item_type},
            },
        },
        TurnResult(),
    )

    assert events == []


@pytest.mark.parametrize("item_type", ["reasoning", "userMessage"])
def test_internal_item_completed_is_not_reported_as_a_tool(item_type: str) -> None:
    events = map_notification(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {"id": "item-1", "type": item_type},
            },
        },
        TurnResult(),
    )

    assert events == []


def test_collab_agent_tool_call_maps_to_agent_tool_event() -> None:
    notification = {
        "method": "item/completed",
        "params": {
            "threadId": "parent-thread",
            "turnId": "turn-1",
            "item": {
                "type": "collabAgentToolCall",
                "id": "call-1",
                "tool": "spawnAgent",
                "status": "completed",
                "senderThreadId": "parent-thread",
                "receiverThreadIds": ["child-thread"],
                "prompt": "child: do work",
                "model": "gpt-5.2",
                "reasoningEffort": "low",
            },
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind == "tool_result"
    assert event.tool_id == "call-1"
    assert event.tool_name == "spawnAgent"
    assert event.source_thread_id == "parent-thread"
    assert event.source_turn_id == "turn-1"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.AGENT
    assert event.tool.status is ToolStatus.COMPLETED
    assert event.agent is not None
    assert event.agent.action == "spawnAgent"
    assert event.agent.sender_thread_id == "parent-thread"
    assert event.agent.receiver_thread_ids == ("child-thread",)
    assert event.agent.prompt == "child: do work"
    assert event.agent.model == "gpt-5.2"
    assert event.agent.reasoning_effort == "low"
    assert event.tool_result == {
        "senderThreadId": "parent-thread",
        "receiverThreadIds": ["child-thread"],
        "prompt": "child: do work",
        "model": "gpt-5.2",
        "reasoningEffort": "low",
    }


def test_collab_tool_call_maps_current_app_server_shape_to_agent_event() -> None:
    notification = {
        "method": "item/completed",
        "params": {
            "threadId": "parent-thread",
            "turnId": "turn-1",
            "item": {
                "type": "collabToolCall",
                "id": "call-1",
                "tool": "spawnAgent",
                "status": "completed",
                "senderThreadId": "parent-thread",
                "receiverThreadId": "child-thread",
                "agentStatus": {"state": "completed"},
                "prompt": "child: do work",
                "model": "gpt-5.4-mini",
                "reasoningEffort": "medium",
            },
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind == "tool_result"
    assert event.tool_id == "call-1"
    assert event.tool_name == "spawnAgent"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.AGENT
    assert event.agent is not None
    assert event.agent.action == "spawnAgent"
    assert event.agent.receiver_thread_ids == ("child-thread",)
    assert event.agent.states == {"state": "completed"}
    assert event.agent.model == "gpt-5.4-mini"
    assert event.agent.reasoning_effort == "medium"
    assert event.tool_result == {
        "senderThreadId": "parent-thread",
        "receiverThreadId": "child-thread",
        "prompt": "child: do work",
        "agentStatus": {"state": "completed"},
        "model": "gpt-5.4-mini",
        "reasoningEffort": "medium",
    }


def test_goal_updated_event_carries_typed_goal_state() -> None:
    notification = {
        "method": "thread/goal/updated",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "goal": {
                "objective": "Finish safely.",
                "status": "paused",
                "tokenBudget": 200_000,
                "tokensUsed": 1200,
                "timeUsedSeconds": 30,
            },
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.GOAL_UPDATED
    assert event.message == "Finish safely."
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"
    assert event.goal is not None
    assert event.goal.objective == "Finish safely."
    assert event.goal.status is GoalStatus.PAUSED
    assert event.goal.token_budget == 200_000
    assert event.goal.tokens_used == 1200
    assert event.goal.time_used_seconds == 30


def test_goal_cleared_event_carries_thread_identity() -> None:
    notification = {
        "method": "thread/goal/cleared",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.GOAL_CLEARED
    assert event.goal is None
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"


def test_unknown_codex_app_notification_is_preserved_as_stream_event() -> None:
    notification = {
        "method": "thread/newProviderThing",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "value": "kept",
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.STREAM_EVENT
    assert event.message == "thread/newProviderThing"
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"
    assert event.raw is notification


def test_account_rate_limits_updated_maps_to_rate_limit_event() -> None:
    notification = {
        "method": "account/rateLimits/updated",
        "params": {
            "rateLimits": {
                "primary": {
                    "usedPercent": 25,
                    "windowDurationMins": 15,
                    "resetsAt": 1730947200,
                },
                "secondary": None,
                "rateLimitReachedType": None,
            }
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.RATE_LIMIT
    assert event.message == "rate limits updated"
    assert event.raw is notification


def test_auto_approval_review_started_maps_to_tool_summary_event() -> None:
    notification = {
        "method": "item/autoApprovalReview/started",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "targetItemId": "cmd-1",
            "review": {"status": "inProgress", "riskLevel": "medium"},
            "action": {"type": "command", "command": "pytest"},
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "auto approval review started: inProgress"
    assert event.tool_id == "cmd-1"
    assert event.tool_name == "item/autoApprovalReview/started"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.status is ToolStatus.STARTED
    assert event.tool_result == {
        "targetItemId": "cmd-1",
        "review": {"status": "inProgress", "riskLevel": "medium"},
        "action": {"type": "command", "command": "pytest"},
    }
    assert event.tool_is_error is False
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"
    assert event.raw is notification


def test_auto_approval_review_completed_denial_is_error_summary_event() -> None:
    notification = {
        "method": "item/autoApprovalReview/completed",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "targetItemId": "patch-1",
            "review": {"status": "denied", "riskLevel": "high"},
            "action": {"type": "applyPatch"},
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "auto approval review completed: denied"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.EDIT
    assert event.tool.status is ToolStatus.COMPLETED
    assert event.tool_is_error is True


def test_file_change_patch_updated_maps_to_edit_summary_event() -> None:
    notification = {
        "method": "item/fileChange/patchUpdated",
        "params": {
            "threadId": "thread-1",
            "turnId": "turn-1",
            "itemId": "edit-1",
            "patch": "@@ -1 +1 @@",
        },
    }

    events = map_notification(notification, TurnResult())

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TOOL_SUMMARY
    assert event.message == "file change patch updated"
    assert event.tool_id == "edit-1"
    assert event.tool_name == "item/fileChange/patchUpdated"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.EDIT
    assert event.tool.status is ToolStatus.STARTED
    assert event.tool_result == {
        "itemId": "edit-1",
        "patch": "@@ -1 +1 @@",
    }
    assert event.tool_is_error is False
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"
    assert event.raw is notification


def test_interrupted_turn_completes_as_cancelled() -> None:
    result = TurnResult()
    process = FakeProcess(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "turn": {"id": "turn-1", "status": "interrupted"},
            },
        }
    )

    step = read_turn_step(process, "thread-1", "turn-1", result, 1.0)

    assert step.done is True
    assert result.status is RunStatus.CANCELLED
    assert step.events[-1].kind == "done"
    assert step.events[-1].message == "codex interrupted"


def test_collab_agent_payload_tolerates_missing_receiver_threads() -> None:
    notification = {
        "method": "item/started",
        "params": {
            "item": {
                "type": "collabAgentToolCall",
                "id": "call-1",
                "tool": "wait",
                "status": "inProgress",
                "senderThreadId": "parent-thread",
            },
        },
    }

    events = map_notification(notification, TurnResult())

    assert events[0].agent is not None
    assert events[0].agent.action == "wait"
    assert events[0].agent.receiver_thread_ids == ()


def test_server_command_approval_request_is_emitted_before_auto_decline() -> None:
    result = TurnResult()
    process = FakeProcess(
        {
            "id": 7,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "cmd-1",
                "command": "pytest",
                "cwd": "/repo",
            },
        }
    )

    step = read_turn_step(process, "thread-1", "turn-1", result, 1.0)

    assert step.done is False
    assert len(step.events) == 1
    event = step.events[0]
    assert event.kind is EventKind.APPROVAL_REQUEST
    assert event.message == "Codex requested command approval"
    assert event.tool_id == "cmd-1"
    assert event.tool_name == "item/commandExecution/requestApproval"
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.command == "pytest"
    assert event.tool.cwd == "/repo"
    assert event.tool.status is ToolStatus.STARTED
    assert event.tool_result == {"decision": "decline"}
    assert event.request is not None
    assert event.request.kind == "approval"
    assert event.request.id == "cmd-1"
    assert event.request.method == "item/commandExecution/requestApproval"
    assert event.request.input == {
        "threadId": "thread-1",
        "turnId": "turn-1",
        "itemId": "cmd-1",
        "command": "pytest",
        "cwd": "/repo",
    }
    assert event.request.default is not None
    assert event.request.default.decision == "decline"
    assert event.response is not None
    assert event.response.decision == "decline"
    assert process.writes == [{"id": 7, "result": {"decision": "decline"}}]


def test_server_request_handler_can_override_response() -> None:
    seen = []
    result = TurnResult()
    process = FakeProcess(
        {
            "id": 7,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "cmd-1",
                "command": "pytest",
            },
        }
    )

    def approve(event, default):
        seen.append((event, default))
        return {"decision": "approve"}

    step = read_turn_step(process, "thread-1", "turn-1", result, 1.0, approve)

    event = step.events[0]
    assert len(seen) == 1
    assert seen[0][0].kind is EventKind.APPROVAL_REQUEST
    assert seen[0][1] == ServerResponse(result={"decision": "decline"})
    assert event.tool_result == {"decision": "approve"}
    assert event.tool_is_error is False
    assert event.response is not None
    assert event.response.decision == "approve"
    assert process.writes == [{"id": 7, "result": {"decision": "approve"}}]


def test_server_request_handler_accepts_neutral_request_policy() -> None:
    result = TurnResult()
    process = FakeProcess(
        {
            "id": 7,
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "cmd-1",
                "command": "pytest",
            },
        }
    )

    event = read_turn_step(
        process,
        "thread-1",
        "turn-1",
        result,
        1.0,
        RequestPolicy.allow_tools(ToolKind.SHELL),
    ).events[0]

    assert event.response is not None
    assert event.response.decision == "accept"
    assert process.writes == [{"id": 7, "result": {"decision": "accept"}}]


def test_server_request_handler_can_return_error_response() -> None:
    result = TurnResult()
    process = FakeProcess(
        {
            "id": 7,
            "method": "item/tool/call",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "callId": "tool-1",
            },
        }
    )

    def reject(event, default):
        return ServerResponse(error={"code": -32000, "message": "blocked"})

    event = read_turn_step(
        process,
        "thread-1",
        "turn-1",
        result,
        1.0,
        reject,
    ).events[0]

    assert event.kind is EventKind.TOOL_REQUEST
    assert event.tool_result == {"code": -32000, "message": "blocked"}
    assert event.tool_is_error is True
    assert process.writes == [
        {"id": 7, "error": {"code": -32000, "message": "blocked"}}
    ]


def test_server_mcp_elicitation_request_maps_to_user_input_event() -> None:
    result = TurnResult()
    process = FakeProcess(
        {
            "id": 8,
            "method": "mcpServer/elicitation/request",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "callId": "form-1",
                "message": "Need input",
            },
        }
    )

    event = read_turn_step(process, "thread-1", "turn-1", result, 1.0).events[0]

    assert event.kind is EventKind.USER_INPUT_REQUEST
    assert event.message == "Codex requested MCP elicitation"
    assert event.tool_id == "form-1"
    assert event.tool is not None
    assert event.tool.kind is ToolKind.MCP
    assert event.tool_result == {"action": "decline", "content": None}
    assert process.writes == [
        {"id": 8, "result": {"action": "decline", "content": None}}
    ]


def test_server_request_resolved_notification_maps_to_event() -> None:
    events = map_notification(
        {
            "method": "serverRequest/resolved",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "cmd-1",
                "method": "item/commandExecution/requestApproval",
                "result": {"decision": "decline"},
            },
        },
        TurnResult(),
    )

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.REQUEST_RESOLVED
    assert event.message == "item/commandExecution/requestApproval resolved"
    assert event.tool_id == "cmd-1"
    assert event.tool_name == "item/commandExecution/requestApproval"
    assert event.tool_result == {"decision": "decline"}
    assert event.tool_is_error is False


class FakeProcess:
    def __init__(self, message):
        self.message = message
        self.writes = []

    def read_until(self, deadline, label):
        return self.message

    def write(self, message):
        self.writes.append(message)
