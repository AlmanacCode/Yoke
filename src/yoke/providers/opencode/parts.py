"""Map OpenCode session 'part' JSON to normalized Yoke events."""

from __future__ import annotations

from yoke.models import (
    AgentCall,
    Event,
    EventKind,
    Surface,
    Tool,
    ToolKind,
    ToolStatus,
    Usage,
)
from yoke.providers.opencode.fields import (
    JsonObject,
    as_record,
    number_field,
    string_field,
    stringify_json_value,
)
from yoke.providers.opencode.usage import parse_opencode_usage

_TOOL_TITLES = {
    ToolKind.READ: "Reading file",
    ToolKind.WRITE: "Writing file",
    ToolKind.EDIT: "Editing file",
    ToolKind.SEARCH: "Searching",
    ToolKind.SHELL: "Running command",
    ToolKind.WEB: "Web request",
    ToolKind.AGENT: "Agent tool",
}


def map_opencode_part(part: JsonObject, session_id: str) -> tuple[Event, ...]:
    part_type = string_field(part, "type")
    if part_type == "text":
        return _text_events(part)
    if part_type == "reasoning":
        return _reasoning_events(part)
    if part_type == "tool":
        return _tool_events(part, session_id)
    if part_type == "patch":
        return _patch_events(part)
    if part_type == "step-finish":
        return _step_finish_events(part)
    return ()


def _text_events(part: JsonObject) -> tuple[Event, ...]:
    text = string_field(part, "text")
    if text is None:
        return ()
    return (
        Event(
            kind=EventKind.TEXT,
            surface=Surface.OPENCODE_SERVER,
            message=text,
            raw=part,
        ),
    )


def _reasoning_events(part: JsonObject) -> tuple[Event, ...]:
    text = string_field(part, "text")
    if text is None:
        return ()
    return (
        Event(
            kind=EventKind.TOOL_SUMMARY,
            surface=Surface.OPENCODE_SERVER,
            message=text,
            raw=part,
        ),
    )


def _tool_events(part: JsonObject, session_id: str) -> tuple[Event, ...]:
    tool_name = string_field(part, "tool") or "tool"
    call_id = string_field(part, "callID")
    state = as_record(part.get("state"))
    tool = opencode_tool(tool_name, state)
    agent = _task_agent_call(part, state, session_id)
    use_event = Event(
        kind=EventKind.TOOL_USE,
        surface=Surface.OPENCODE_SERVER,
        message=tool.title or tool_name,
        tool_id=call_id,
        tool_name=tool_name,
        tool_input=stringify_json_value(state.get("input")),
        tool=tool,
        agent=agent,
        source_thread_id=session_id,
        raw=part,
    )
    result_event = Event(
        kind=EventKind.TOOL_RESULT,
        surface=Surface.OPENCODE_SERVER,
        message=tool.title or f"{tool_name} completed",
        tool_id=call_id,
        tool_name=tool_name,
        tool=tool,
        tool_result=state.get("output"),
        tool_is_error=tool.status == ToolStatus.FAILED,
        agent=agent,
        source_thread_id=session_id,
        raw=part,
    )
    return (use_event, result_event)


def _task_agent_call(
    part: JsonObject,
    state: JsonObject,
    session_id: str,
) -> AgentCall | None:
    if string_field(part, "tool") != "task":
        return None
    metadata = as_record(state.get("metadata"))
    child_session_id = string_field(metadata, "sessionId")
    if child_session_id is None:
        return None
    input_record = as_record(state.get("input"))
    prompt = string_field(input_record, "prompt") or string_field(
        input_record, "description"
    )
    status = string_field(state, "status")
    action = "completed" if status in ("completed", "error") else "spawned"
    return AgentCall(
        action=action,
        agent_type="task",
        sender_thread_id=session_id,
        new_thread_id=child_session_id,
        prompt=prompt,
    )


def opencode_tool(tool_name: str, state: JsonObject) -> Tool:
    metadata = as_record(state.get("metadata"))
    input_record = as_record(state.get("input"))
    kind = infer_opencode_tool_kind(tool_name)
    return Tool(
        kind=kind,
        title=string_field(state, "title") or _TOOL_TITLES.get(kind, tool_name),
        path=string_field(input_record, "filePath")
        or string_field(input_record, "path"),
        command=string_field(input_record, "command"),
        status=opencode_tool_status(state),
        exit_code=number_field(metadata, "exit"),
    )


def opencode_tool_status(state: JsonObject) -> ToolStatus:
    status = string_field(state, "status")
    if status == "error":
        return ToolStatus.FAILED
    return ToolStatus.COMPLETED


def infer_opencode_tool_kind(tool: str) -> ToolKind:
    normalized = tool.lower()
    if "read" in normalized:
        return ToolKind.READ
    if "write" in normalized:
        return ToolKind.WRITE
    if "edit" in normalized or "patch" in normalized:
        return ToolKind.EDIT
    if any(word in normalized for word in ("grep", "glob", "search", "find", "ls")):
        return ToolKind.SEARCH
    if "bash" in normalized or "shell" in normalized:
        return ToolKind.SHELL
    if "web" in normalized or "fetch" in normalized:
        return ToolKind.WEB
    if "task" in normalized or "agent" in normalized:
        return ToolKind.AGENT
    return ToolKind.UNKNOWN


def _patch_events(part: JsonObject) -> tuple[Event, ...]:
    files = part.get("files")
    if not isinstance(files, list) or len(files) == 0:
        return ()
    names = ", ".join(str(item) for item in files)
    return (
        Event(
            kind=EventKind.TOOL_SUMMARY,
            surface=Surface.OPENCODE_SERVER,
            message=f"files changed: {names}",
            raw=part,
        ),
    )


def _step_finish_events(part: JsonObject) -> tuple[Event, ...]:
    usage = parse_opencode_usage(part.get("tokens"))
    if usage is None:
        return ()
    return (
        Event(
            kind=EventKind.CONTEXT_USAGE,
            surface=Surface.OPENCODE_SERVER,
            message=usage_message(usage),
            usage=usage,
            raw=part,
        ),
    )


def usage_message(usage: Usage) -> str:
    if usage.total_tokens is not None:
        return f"usage: {usage.total_tokens} tokens"
    return "usage updated"


def final_text_from_parts(parts: list[JsonObject]) -> str | None:
    for part in reversed(parts):
        if string_field(part, "type") == "text":
            text = string_field(part, "text")
            if text is not None:
                return text
    return None


def is_task_spawn(part: JsonObject) -> tuple[str, str] | None:
    """(child_session_id, prompt) if this part spawns a sub-agent session."""

    if string_field(part, "type") != "tool" or string_field(part, "tool") != "task":
        return None
    state = as_record(part.get("state"))
    metadata = as_record(state.get("metadata"))
    child_session_id = string_field(metadata, "sessionId")
    if child_session_id is None:
        return None
    input_record = as_record(state.get("input"))
    prompt = string_field(input_record, "prompt") or string_field(
        input_record, "description"
    )
    return child_session_id, (prompt or "")
