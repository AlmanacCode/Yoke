"""Codex app-server notification mapping."""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass, field
from typing import Iterator

from pydantic import JsonValue

from yoke.errors import YokeError
from yoke.models import Event, Tool, ToolKind, ToolStatus, Usage
from yoke.providers.codex_app.fields import (
    JsonObject,
    as_record,
    compact_json,
    first_present,
    number_field,
    string_field,
)
from yoke.providers.codex_app.process import JsonRpcLineProcess, is_server_request
from yoke.providers.codex_app.rpc import respond_to_server_request


@dataclass
class TurnResult:
    output: str = ""
    events: list[Event] = field(default_factory=list)
    usage: Usage | None = None


@dataclass
class TurnStep:
    events: list[Event] = field(default_factory=list)
    done: bool = False


def read_turn(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    timeout_seconds: float,
) -> TurnResult:
    result = TurnResult()
    deadline = time.monotonic() + timeout_seconds
    for step in iter_turn(process, thread_id, turn_id, result, deadline):
        result.events.extend(step.events)
    return result


def iter_turn(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    result: TurnResult,
    deadline: float,
) -> Iterator[TurnStep]:
    while True:
        step = read_turn_step(process, thread_id, turn_id, result, deadline)
        yield step
        if step.done:
            return


def read_turn_step(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    result: TurnResult,
    deadline: float,
) -> TurnStep:
    while True:
        message = process.read_until(deadline, "turn timed out")
        if is_server_request(message):
            respond_to_server_request(process, message)
            continue
        method = string_field(message, "method")
        if method is None:
            continue
        events = map_notification(message, result)
        if method == "error":
            detail = result.output or "Codex app-server error"
            raise YokeError(detail)
        if method == "turn/completed" and is_root_turn(message, thread_id, turn_id):
            error = turn_error(message)
            if error:
                raise YokeError(error)
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
        goal = as_record(params.get("goal"))
        objective = string_field(goal, "objective")
        return [
            Event(
                kind="goal_updated",
                message=objective or "goal updated",
                raw=notification,
            )
        ]
    if method == "thread/goal/cleared":
        return [Event(kind="goal_cleared", message="goal cleared", raw=notification)]
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
    return []


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
    if item_type == "collabAgentToolCall":
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
    if item_type == "collabAgentToolCall":
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
    return string_field(item, "type") or "tool"


def tool_result(item: JsonObject) -> JsonValue | None:
    for name in ("aggregatedOutput", "result", "error"):
        value = item.get(name)
        if value is not None:
            return value
    return None


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
