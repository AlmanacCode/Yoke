"""Codex app-server notification mapping."""

from __future__ import annotations

import base64
import binascii
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from pydantic import JsonValue

from yoke.models import (
    AgentCall,
    Event,
    Failure,
    Request,
    RequestKind,
    Response,
    RunStatus,
    Tool,
    ToolKind,
    ToolStatus,
    Usage,
)
from yoke.providers.codex_app.fields import (
    JsonObject,
    as_record,
    compact_json,
    first_present,
    number_field,
    string_field,
)
from yoke.providers.codex_app.goals import yoke_goal
from yoke.providers.codex_app.process import JsonRpcLineProcess, is_server_request
from yoke.providers.codex_app.rpc import (
    ServerResponse,
    noninteractive_response,
    normalize_server_response,
    respond_to_server_request,
)


@dataclass
class TurnResult:
    output: str = ""
    status: RunStatus = RunStatus.SUCCEEDED
    events: list[Event] = field(default_factory=list)
    usage: Usage | None = None
    failure: Failure | None = None


@dataclass
class TurnStep:
    events: list[Event] = field(default_factory=list)
    done: bool = False


def read_turn(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    timeout_seconds: float,
    request_handler: object | None = None,
    on_event: Callable[[Event], None] | None = None,
) -> TurnResult:
    result = TurnResult()
    deadline = time.monotonic() + timeout_seconds
    for step in iter_turn(
        process,
        thread_id,
        turn_id,
        result,
        deadline,
        request_handler,
    ):
        if on_event is not None:
            for event in step.events:
                on_event(event)
        result.events.extend(step.events)
    return result


def iter_turn(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    result: TurnResult,
    deadline: float,
    request_handler: object | None = None,
) -> Iterator[TurnStep]:
    while True:
        step = read_turn_step(
            process,
            thread_id,
            turn_id,
            result,
            deadline,
            request_handler,
        )
        yield step
        if step.done:
            return


def read_turn_step(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    result: TurnResult,
    deadline: float,
    request_handler: object | None = None,
) -> TurnStep:
    while True:
        message = process.read_until(deadline, "turn timed out")
        if is_server_request(message):
            default = default_server_response(message)
            event = server_request_event(message, default)
            response = policy_server_response(event, default, request_handler)
            event = event_for_server_response(event, response)
            respond_to_server_request(process, message, response)
            return TurnStep(events=[event])
        method = string_field(message, "method")
        if method is None:
            continue
        events = map_notification(message, result)
        if method == "error":
            detail = result.output or "Codex app-server error"
            result.status = RunStatus.FAILED
            result.failure = Failure(
                message=detail,
                raw=compact_json(message),
            )
            events.append(Event(kind="error", message=detail, raw=message))
            return TurnStep(events=events, done=True)
        if method == "turn/completed" and is_root_turn(message, thread_id, turn_id):
            error = turn_error(message)
            if error:
                result.status = RunStatus.FAILED
                result.failure = Failure(message=error, raw=compact_json(message))
                events.append(Event(kind="error", message=error, raw=message))
                return TurnStep(events=events, done=True)
            status = turn_status(message)
            if status == "interrupted":
                result.status = RunStatus.CANCELLED
                events.append(Event(kind="done", message="codex interrupted"))
                return TurnStep(events=events, done=True)
            events.append(Event(kind="done", message="codex completed"))
            return TurnStep(events=events, done=True)
        if events:
            return TurnStep(events=events)


def map_notification(notification: JsonObject, result: TurnResult) -> list[Event]:
    method = string_field(notification, "method")
    params = as_record(notification.get("params"))
    thread_id = string_field(params, "threadId")
    turn_id = string_field(params, "turnId")
    if method == "item/agentMessage/delta":
        delta = string_field(params, "delta")
        if delta is None:
            return []
        return [
            Event(
                kind="text_delta",
                message=delta,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method in {
        "item/plan/delta",
        "item/commandExecution/outputDelta",
        "command/exec/outputDelta",
        "item/fileChange/outputDelta",
    }:
        delta = output_delta(params)
        if delta is None:
            return []
        return [
            Event(
                kind="tool_summary",
                message=delta,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "turn/plan/updated":
        summary = plan_summary(params)
        if summary is None:
            return []
        return [
            Event(
                kind="tool_summary",
                message=summary,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "thread/tokenUsage/updated":
        usage = parse_app_server_usage(params.get("tokenUsage"))
        result.usage = usage
        return [
            Event(
                kind="context_usage",
                message=usage_message(usage),
                usage=usage,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "account/rateLimits/updated":
        return [
            Event(
                kind="rate_limit",
                message="rate limits updated",
                raw=notification,
            )
        ]
    if method in {
        "item/autoApprovalReview/started",
        "item/autoApprovalReview/completed",
    }:
        return [auto_approval_review_event(method, params, notification)]
    if method == "item/fileChange/patchUpdated":
        return [file_change_patch_updated_event(params, notification)]
    if method == "item/started":
        item = as_record(params.get("item"))
        return [tool_event("tool_use", item, ToolStatus.STARTED, params, notification)]
    if method == "item/completed":
        item = as_record(params.get("item"))
        if string_field(item, "type") == "agentMessage":
            text = string_field(item, "text")
            if text is None:
                return []
            result.output = text
            return [
                Event(
                    kind="text",
                    message=text,
                    source_thread_id=thread_id,
                    source_turn_id=turn_id,
                    raw=notification,
                )
            ]
        return [
            tool_event(
                "tool_result",
                item,
                item_status(item, ToolStatus.COMPLETED),
                params,
                notification,
            )
        ]
    if method == "thread/goal/updated":
        goal = yoke_goal(as_record(params.get("goal")))
        return [
            Event(
                kind="goal_updated",
                message=goal.objective if goal is not None else "goal updated",
                goal=goal,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "thread/goal/cleared":
        return [
            Event(
                kind="goal_cleared",
                message="goal cleared",
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "serverRequest/resolved":
        return [server_request_resolved_event(params, notification)]
    if method == "warning":
        message = string_field(params, "message") or "Codex warning"
        return [
            Event(
                kind="warning",
                message=message,
                source_thread_id=thread_id,
                source_turn_id=turn_id,
                raw=notification,
            )
        ]
    if method == "error":
        error = as_record(params.get("error"))
        message = string_field(error, "message") or string_field(params, "message")
        result.output = message or "Codex app-server error"
        return [Event(kind="error", message=result.output, raw=notification)]
    return [
        Event(
            kind="stream_event",
            message=method,
            source_thread_id=thread_id,
            source_turn_id=turn_id,
            raw=notification,
        )
    ]


def server_request_event(message: JsonObject, response: ServerResponse) -> Event:
    method = string_field(message, "method") or "request"
    params = as_record(message.get("params"))
    request_id = first_present(
        string_field(params, "itemId"),
        string_field(params, "callId"),
        str(message.get("id")) if message.get("id") is not None else None,
    )
    tool = server_request_tool(method, params)
    default_response = response_model(response)
    return Event(
        kind=server_request_kind(method),
        message=server_request_message(method),
        tool_id=request_id,
        tool_name=method,
        tool_input=compact_json(params),
        tool=tool,
        tool_result=response.result if response.error is None else response.error,
        tool_is_error=response.error is not None,
        request=Request(
            kind=server_request_request_kind(method),
            id=request_id,
            method=method,
            message=server_request_message(method),
            tool=tool,
            input=params,
            default=default_response,
            raw=message,
        ),
        response=default_response,
        source_thread_id=string_field(params, "threadId"),
        source_turn_id=string_field(params, "turnId"),
        raw=message,
    )


def default_server_response(message: JsonObject) -> ServerResponse:
    return noninteractive_response(string_field(message, "method") or "request")


def policy_server_response(
    event: Event,
    default: ServerResponse,
    request_handler: object | None,
) -> ServerResponse:
    if request_handler is None:
        return default
    if not callable(request_handler):
        return default
    response = request_handler(event, default)
    if response is None:
        return default
    if isinstance(response, Response):
        return codex_response_from_yoke(event, response)
    return normalize_server_response(response)


def event_for_server_response(event: Event, response: ServerResponse) -> Event:
    result = response.result if response.error is None else response.error
    return event.model_copy(
        update={
            "tool_result": result,
            "tool_is_error": response.error is not None,
            "response": response_model(response),
        }
    )


def server_request_resolved_event(params: JsonObject, raw: JsonObject) -> Event:
    method = string_field(params, "method") or "server request"
    return Event(
        kind="request_resolved",
        message=f"{method} resolved",
        tool_id=first_present(
            string_field(params, "itemId"),
            string_field(params, "callId"),
            string_field(params, "requestId"),
        ),
        tool_name=method,
        tool_result=params.get("result"),
        tool_is_error=params.get("error") is not None,
        source_thread_id=string_field(params, "threadId"),
        source_turn_id=string_field(params, "turnId"),
        raw=raw,
    )


def auto_approval_review_event(
    method: str,
    params: JsonObject,
    raw: JsonObject,
) -> Event:
    completed = method.endswith("/completed")
    review = as_record(params.get("review"))
    status = string_field(review, "status")
    message = (
        "auto approval review completed"
        if completed
        else "auto approval review started"
    )
    return Event(
        kind="tool_summary",
        message=f"{message}: {status}" if status else message,
        tool_id=string_field(params, "targetItemId"),
        tool_name=method,
        tool=Tool(
            kind=review_action_kind(as_record(params.get("action"))),
            title="Auto approval review",
            status=ToolStatus.COMPLETED if completed else ToolStatus.STARTED,
            summary=status,
        ),
        tool_result={
            key: params[key]
            for key in ("targetItemId", "review", "action")
            if key in params
        },
        tool_is_error=status in {"denied", "aborted"},
        source_thread_id=string_field(params, "threadId"),
        source_turn_id=string_field(params, "turnId"),
        raw=raw,
    )


def file_change_patch_updated_event(params: JsonObject, raw: JsonObject) -> Event:
    item_id = first_present(
        string_field(params, "itemId"),
        string_field(params, "targetItemId"),
    )
    return Event(
        kind="tool_summary",
        message="file change patch updated",
        tool_id=item_id,
        tool_name="item/fileChange/patchUpdated",
        tool=Tool(
            kind=ToolKind.EDIT,
            title="File change patch updated",
            status=ToolStatus.STARTED,
        ),
        tool_result={
            key: params[key]
            for key in ("itemId", "targetItemId", "patch", "diff", "changes")
            if key in params
        },
        tool_is_error=False,
        source_thread_id=string_field(params, "threadId"),
        source_turn_id=string_field(params, "turnId"),
        raw=raw,
    )


def review_action_kind(action: JsonObject) -> ToolKind:
    action_type = string_field(action, "type")
    if action_type in {"command", "execve"}:
        return ToolKind.SHELL
    if action_type == "applyPatch":
        return ToolKind.EDIT
    if action_type == "networkAccess":
        return ToolKind.WEB
    if action_type == "mcpToolCall":
        return ToolKind.MCP
    return ToolKind.UNKNOWN


def server_request_kind(method: str) -> str:
    if method in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "execCommandApproval",
        "applyPatchApproval",
        "item/permissions/requestApproval",
    }:
        return "approval_request"
    if method in {"item/tool/requestUserInput", "mcpServer/elicitation/request"}:
        return "user_input_request"
    return "tool_request"


def server_request_request_kind(method: str) -> RequestKind:
    if method == "item/permissions/requestApproval":
        return RequestKind.PERMISSION
    if server_request_kind(method) == "approval_request":
        return RequestKind.APPROVAL
    if server_request_kind(method) == "user_input_request":
        return RequestKind.USER_INPUT
    if server_request_kind(method) == "tool_request":
        return RequestKind.TOOL
    return RequestKind.UNKNOWN


def response_model(response: ServerResponse) -> Response:
    result = response.result
    result_object = as_record(result)
    answers = result_object.get("answers")
    return Response(
        result=result,
        error=response.error,
        decision=string_field(result_object, "decision")
        or string_field(result_object, "action"),
        answers=answers if isinstance(answers, dict) else None,
        raw={"result": response.result, "error": response.error},
    )


def codex_response_from_yoke(event: Event, response: Response) -> ServerResponse:
    """Lower a Yoke request response to Codex app-server JSON-RPC result."""

    method = event.request.method if event.request is not None else event.tool_name
    if method in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "execCommandApproval",
        "applyPatchApproval",
    }:
        decision = "accept" if response.decision in ALLOW_DECISIONS else "decline"
        return ServerResponse(result={"decision": decision})
    if method == "item/permissions/requestApproval":
        if response.decision in ALLOW_DECISIONS:
            return ServerResponse(
                result={
                    "permissions": response.result or {},
                    "scope": "turn",
                    "strictAutoReview": True,
                }
            )
        return ServerResponse(
            result={"permissions": {}, "scope": "turn", "strictAutoReview": True}
        )
    if method == "item/tool/requestUserInput":
        return ServerResponse(result={"answers": response.answers or {}})
    if method == "mcpServer/elicitation/request":
        if response.decision in ALLOW_DECISIONS:
            return ServerResponse(
                result={"action": "accept", "content": response.result}
            )
        return ServerResponse(result={"action": "decline", "content": None})
    if method == "item/tool/call":
        if response.decision in ALLOW_DECISIONS:
            return ServerResponse(
                result={"contentItems": response.result or [], "success": True}
            )
        return ServerResponse(result={"contentItems": [], "success": False})
    if response.error is not None:
        return ServerResponse(error=as_record(response.error))
    return ServerResponse(result=as_record(response.result))


ALLOW_DECISIONS = {"allow", "approve", "accept", "acceptForSession"}


def server_request_message(method: str) -> str:
    return {
        "item/commandExecution/requestApproval": "Codex requested command approval",
        "item/fileChange/requestApproval": "Codex requested file change approval",
        "execCommandApproval": "Codex requested command approval",
        "applyPatchApproval": "Codex requested patch approval",
        "item/tool/requestUserInput": "Codex requested user input",
        "mcpServer/elicitation/request": "Codex requested MCP elicitation",
        "item/tool/call": "Codex requested tool call",
        "item/permissions/requestApproval": "Codex requested permissions approval",
    }.get(method, f"Codex requested {method}")


def server_request_tool(method: str, params: JsonObject) -> Tool:
    if "commandExecution" in method or method == "execCommandApproval":
        return Tool(
            kind=ToolKind.SHELL,
            title="Command approval",
            command=string_field(params, "command"),
            cwd=string_field(params, "cwd"),
            status=ToolStatus.STARTED,
        )
    if "fileChange" in method or method == "applyPatchApproval":
        return Tool(
            kind=ToolKind.EDIT,
            title="File change approval",
            path=first_present(
                string_field(params, "path"),
                string_field(params, "filePath"),
            ),
            status=ToolStatus.STARTED,
        )
    if method == "mcpServer/elicitation/request":
        return Tool(
            kind=ToolKind.MCP,
            title="MCP elicitation",
            status=ToolStatus.STARTED,
        )
    if method == "item/permissions/requestApproval":
        return Tool(
            kind=ToolKind.UNKNOWN,
            title="Permissions approval",
            status=ToolStatus.STARTED,
        )
    return Tool(kind=ToolKind.UNKNOWN, title=method, status=ToolStatus.STARTED)


def is_root_turn(notification: JsonObject, thread_id: str, turn_id: str | None) -> bool:
    if string_field(notification, "method") != "turn/completed":
        return False
    params = as_record(notification.get("params"))
    completed_turn_id = string_field(params, "turnId")
    completed_thread_id = string_field(params, "threadId")
    return completed_turn_id == turn_id or completed_thread_id == thread_id


def turn_error(notification: JsonObject) -> str | None:
    params = as_record(notification.get("params"))
    turn = as_record(params.get("turn"))
    error = as_record(turn.get("error"))
    return string_field(error, "message")


def turn_status(notification: JsonObject) -> str | None:
    params = as_record(notification.get("params"))
    turn = as_record(params.get("turn"))
    return string_field(turn, "status") or string_field(params, "status")


def plan_summary(params: JsonObject) -> str | None:
    parts: list[str] = []
    explanation = string_field(params, "explanation")
    if explanation is not None:
        parts.append(explanation)
    plan = params.get("plan")
    if isinstance(plan, list):
        for item in plan:
            step = string_field(as_record(item), "step")
            if step is not None:
                parts.append(step)
    return " | ".join(parts) or None


def item_title(item: JsonObject) -> str:
    item_type = string_field(item, "type")
    if item_type == "commandExecution":
        return "Running command"
    if item_type == "fileChange":
        return "Editing file"
    if item_type == "mcpToolCall":
        return f"MCP {string_field(item, 'tool') or 'tool'}"
    if is_collab_tool_call(item):
        return f"Agent {string_field(item, 'tool') or 'tool'}"
    return item_type or "Tool"


def tool_event(
    kind: str,
    item: JsonObject,
    status: ToolStatus,
    params: JsonObject,
    raw: JsonObject,
) -> Event:
    tool = tool_display(item, status)
    return Event(
        kind=kind,
        message=tool.title or item_type_tool_name(item),
        tool_id=string_field(item, "id"),
        tool_name=item_type_tool_name(item),
        tool_input=compact_json(item),
        tool=tool,
        tool_result=tool_result(item),
        tool_is_error=tool.status in {ToolStatus.FAILED, ToolStatus.DECLINED},
        agent=agent_call(item),
        source_thread_id=string_field(params, "threadId"),
        source_turn_id=string_field(params, "turnId"),
        raw=raw,
    )


def tool_display(item: JsonObject, fallback_status: ToolStatus) -> Tool:
    item_type = string_field(item, "type")
    status = item_status(item, fallback_status)
    if item_type == "commandExecution":
        action = first_command_action(item)
        action_type = string_field(action, "type")
        if action_type == "read":
            kind = ToolKind.READ
            title = "Reading file"
        elif action_type in {"listFiles", "search"}:
            kind = ToolKind.SEARCH
            title = "Searching"
        else:
            kind = ToolKind.SHELL
            title = "Running command"
        return Tool(
            kind=kind,
            title=title,
            path=string_field(action, "path"),
            command=string_field(item, "command"),
            cwd=string_field(item, "cwd"),
            status=status,
            exit_code=number_field(item, "exitCode"),
            duration_ms=number_field(item, "durationMs"),
        )
    if item_type == "fileChange":
        return Tool(
            kind=ToolKind.EDIT,
            title="Editing file",
            status=status,
            duration_ms=number_field(item, "durationMs"),
        )
    if item_type == "mcpToolCall":
        return Tool(
            kind=ToolKind.MCP,
            title=f"MCP {string_field(item, 'tool') or 'tool'}",
            status=status,
        )
    if item_type == "dynamicToolCall":
        tool = string_field(item, "tool") or "Tool"
        return Tool(kind=infer_tool_kind(tool), title=tool_title(tool), status=status)
    if item_type == "webSearch":
        return Tool(
            kind=ToolKind.WEB,
            title="Web search",
            summary=string_field(item, "query"),
            status=status,
        )
    if item_type == "imageView":
        return Tool(
            kind=ToolKind.IMAGE,
            title="Viewing image",
            path=string_field(item, "path"),
            status=status,
        )
    if is_collab_tool_call(item):
        return Tool(
            kind=ToolKind.AGENT,
            title=f"Agent {string_field(item, 'tool') or 'tool'}",
            status=status,
        )
    return Tool(kind=ToolKind.UNKNOWN, title=item_title(item), status=status)


def item_status(item: JsonObject, fallback: ToolStatus) -> ToolStatus:
    status = string_field(item, "status")
    if status == "completed":
        return ToolStatus.COMPLETED
    if status == "failed":
        return ToolStatus.FAILED
    if status == "declined":
        return ToolStatus.DECLINED
    return fallback


def first_command_action(item: JsonObject) -> JsonObject:
    actions = item.get("commandActions")
    if isinstance(actions, list) and actions:
        return as_record(actions[0])
    return {}


def infer_tool_kind(tool: str) -> ToolKind:
    normalized = tool.lower()
    if "read" in normalized:
        return ToolKind.READ
    if "write" in normalized:
        return ToolKind.WRITE
    if "edit" in normalized or "patch" in normalized:
        return ToolKind.EDIT
    if "search" in normalized or "find" in normalized:
        return ToolKind.SEARCH
    if "bash" in normalized or "shell" in normalized:
        return ToolKind.SHELL
    if "agent" in normalized:
        return ToolKind.AGENT
    return ToolKind.UNKNOWN


def tool_title(tool: str) -> str:
    kind = infer_tool_kind(tool)
    if kind == ToolKind.READ:
        return "Reading file"
    if kind == ToolKind.WRITE:
        return "Writing file"
    if kind == ToolKind.EDIT:
        return "Editing file"
    if kind == ToolKind.SEARCH:
        return "Searching"
    if kind == ToolKind.SHELL:
        return "Running command"
    if kind == ToolKind.AGENT:
        return "Agent tool"
    return tool


def item_type_tool_name(item: JsonObject) -> str:
    if is_collab_tool_call(item):
        return (
            string_field(item, "tool")
            or string_field(item, "type")
            or "collabToolCall"
        )
    return string_field(item, "type") or "tool"


def tool_result(item: JsonObject) -> JsonValue | None:
    if is_collab_tool_call(item):
        result = {
            key: item[key]
            for key in (
                "senderThreadId",
                "receiverThreadId",
                "receiverThreadIds",
                "newThreadId",
                "prompt",
                "agentStatus",
                "agentsStates",
                "model",
                "reasoningEffort",
            )
            if key in item
        }
        return result or None
    for name in ("aggregatedOutput", "result", "error"):
        value = item.get(name)
        if value is not None:
            return value
    return None


def agent_call(item: JsonObject) -> AgentCall | None:
    if not is_collab_tool_call(item):
        return None
    receivers = collab_receiver_thread_ids(item)
    return AgentCall(
        action=string_field(item, "tool"),
        sender_thread_id=string_field(item, "senderThreadId"),
        receiver_thread_ids=receivers,
        new_thread_id=string_field(item, "newThreadId"),
        prompt=string_field(item, "prompt"),
        model=string_field(item, "model"),
        reasoning_effort=string_field(item, "reasoningEffort"),
        states=first_present(item.get("agentStatus"), item.get("agentsStates")),
    )


def is_collab_tool_call(item: JsonObject) -> bool:
    return string_field(item, "type") in {"collabToolCall", "collabAgentToolCall"}


def collab_receiver_thread_ids(item: JsonObject) -> tuple[str, ...]:
    receiver = string_field(item, "receiverThreadId")
    if receiver is not None:
        return (receiver,)
    receivers = item.get("receiverThreadIds")
    if isinstance(receivers, list):
        return tuple(str(receiver) for receiver in receivers)
    return ()


def output_delta(params: JsonObject) -> str | None:
    delta = string_field(params, "delta")
    if delta is not None:
        return delta
    encoded = string_field(params, "deltaBase64")
    if encoded is None:
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return encoded


def parse_app_server_usage(value: JsonValue | None) -> Usage:
    usage = as_record(value)
    last = as_record(usage.get("last"))
    total = as_record(usage.get("total"))
    parsed = parse_usage(last)
    return parsed.model_copy(
        update={
            "total_tokens": first_present(
                number_field(last, "totalTokens"),
                number_field(last, "total_tokens"),
                parsed.total_tokens,
            ),
            "total_processed_tokens": first_present(
                number_field(total, "totalTokens"),
                number_field(total, "total_tokens"),
            ),
            "max_tokens": first_present(
                number_field(usage, "modelContextWindow"),
                number_field(usage, "model_context_window"),
            ),
        }
    )


def parse_usage(value: JsonValue | None) -> Usage:
    obj = as_record(value)
    input_tokens = first_present(
        number_field(obj, "input_tokens"),
        number_field(obj, "inputTokens"),
    )
    cached_input_tokens = first_present(
        number_field(obj, "cached_input_tokens"),
        number_field(obj, "cachedInputTokens"),
        number_field(obj, "cacheReadTokens"),
    )
    output_tokens = first_present(
        number_field(obj, "output_tokens"),
        number_field(obj, "outputTokens"),
    )
    reasoning_output_tokens = first_present(
        number_field(obj, "reasoning_output_tokens"),
        number_field(obj, "reasoningOutputTokens"),
    )
    total_tokens = None
    if input_tokens is not None or output_tokens is not None:
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return Usage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
        total_tokens=total_tokens,
    )


def usage_message(usage: Usage) -> str:
    if usage.total_tokens is not None:
        return f"usage: {usage.total_tokens} tokens"
    return "usage updated"
