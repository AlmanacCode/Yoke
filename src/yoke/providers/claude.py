"""Claude Agent SDK adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from yoke.capabilities import Capabilities, Feature, Support
from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Access,
    Agent,
    Approval,
    Event,
    Goal,
    Harness,
    Provider,
    Run,
    Session,
    Turn,
    Usage,
)
from yoke.options import RunOptions, SessionOptions
from yoke.providers.claude_plugins import is_plugin_skill_path, plugin_paths


class Claude:
    """Adapter for Claude Agent SDK."""

    provider: Provider = "claude"
    surface = "claude_python_sdk"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.STREAMING: Support.NATIVE,
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.FILESYSTEM_AGENT: Support.NATIVE,
            Feature.INLINE_SUBAGENTS: Support.NATIVE,
            Feature.DECLARED_SUBAGENTS: Support.COMPILED,
            Feature.SKILLS: (
                Support.NATIVE,
                "Yoke folder skills load as local Claude plugins; inline skills "
                "still compile into prompt text.",
            ),
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: (
                Support.COMPILED,
                "Claude receives Yoke goals through prompt and task_budget.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.WORKFLOW: Support.EMULATED,
        }
    )

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        """Execute a one-shot Claude run."""

        try:
            from claude_agent_sdk import query
        except ImportError as exc:
            raise YokeError(
                "Claude support requires `pip install yoke[claude]`."
            ) from exc

        messages = query(prompt=prompt, options=claude_options(harness, options))
        return await collect_messages(self.provider, messages)

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        """Start a Claude session.

        ClaudeSDKClient owns a live subprocess and must be closed by the caller.
        """

        try:
            from claude_agent_sdk import ClaudeSDKClient
        except ImportError as exc:
            raise YokeError(
                "Claude support requires `pip install yoke[claude]`."
            ) from exc

        run_options = RunOptions(
            goal=options.goal,
            effort=options.effort,
            permissions=options.permissions,
            provider=options.provider,
        )
        client = ClaudeSDKClient(options=claude_options(harness, run_options))
        await client.connect()
        session_id = options.resume or str(uuid4())
        self._clients[session_id] = client
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=session_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=options.permissions or harness.permissions or harness.agent.permissions,
            goal=options.goal or harness.agent.goal,
        )

    async def send(self, session: Session, turn: Turn) -> Run:
        client = self._clients.get(session.id)
        if client is None:
            raise YokeError(f"Claude session is not live: {session.id}")
        await client.query(turn.prompt, session_id=session.id)
        return await collect_messages(self.provider, client.receive_response(), session)

    async def stream(self, session: Session, turn: Turn) -> AsyncIterator[Event]:
        client = self._clients.get(session.id)
        if client is None:
            raise YokeError(f"Claude session is not live: {session.id}")
        await client.query(turn.prompt, session_id=session.id)
        async for message in client.receive_response():
            for event in claude_events(message):
                yield event

    async def get_goal(self, session: Session) -> Goal | None:
        raise UnsupportedFeature("Claude does not expose native readable goals.")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")

    async def close(self, session: Session) -> None:
        client = self._clients.pop(session.id, None)
        if client is not None:
            await client.disconnect()


def claude_options(harness: Harness, options: RunOptions):
    try:
        from claude_agent_sdk import ClaudeAgentOptions
        from claude_agent_sdk import AgentDefinition as ClaudeAgentDefinition
    except ImportError as exc:
        raise YokeError("Claude support requires `pip install yoke[claude]`.") from exc

    agent = harness.agent
    goal = options.goal or agent.goal
    plugins = claude_plugins(agent)
    return ClaudeAgentOptions(
        system_prompt=system_prompt(agent, goal),
        cwd=harness.cwd,
        model=agent.model,
        effort=options.effort or agent.effort,
        max_turns=options.max_turns,
        permission_mode=permission_mode(harness, options.permissions),
        tools=tools(agent),
        allowed_tools=allowed_tools(agent, harness, options.permissions),
        disallowed_tools=disallowed_tools(agent),
        agents={
            name: ClaudeAgentDefinition(
                description=subagent.description or name,
                prompt=subagent.instructions or subagent.description or name,
                tools=claude_tools(subagent),
                model=subagent.model,
                skills=skill_names(subagent),
                effort=subagent.effort,
                permissionMode=permission_mode_for_agent(subagent),
            )
            for name, subagent in agent.subagents.items()
        }
        or None,
        plugins=plugins or [],
        skills="all" if plugins else skill_names(agent) or None,
        output_format=output_format(options.output_schema),
        task_budget={"total": goal.token_budget}
        if goal and goal.token_budget is not None
        else None,
    )


async def collect_messages(
    provider: Provider,
    messages: AsyncIterator[Any],
    session: Session | None = None,
) -> Run:
    events: list[Event] = []
    text: list[str] = []
    fallback_result: str | None = None
    usage: Usage | None = None
    async for message in messages:
        mapped = claude_events(message)
        events.extend(mapped)
        for event in mapped:
            if event.kind == "text" and event.message is not None:
                text.append(event.message)
            if event.usage is not None:
                usage = event.usage
        if type(message).__name__ == "ResultMessage":
            structured_output = getattr(message, "structured_output", None)
            result_text = getattr(message, "result", None)
            if structured_output is not None:
                fallback_result = str(structured_output)
            elif result_text:
                fallback_result = str(result_text)
    return Run(
        provider=provider,
        output=("\n".join(text).strip() or fallback_result),
        events=tuple(events),
        session=session,
        usage=usage,
    )


def claude_events(message: Any) -> list[Event]:
    """Map Claude SDK messages into small Yoke events."""

    name = type(message).__name__
    if name == "AssistantMessage":
        return assistant_events(message)
    if name == "ResultMessage":
        return result_events(message)
    if name == "SystemMessage":
        data = getattr(message, "data", {}) or {}
        session_id = data.get("session_id") if isinstance(data, dict) else None
        return [
            Event(
                kind="provider_session",
                message=str(getattr(message, "subtype", "system")),
                provider_session_id=str(session_id) if session_id else None,
                raw=message,
            )
        ]
    if name == "StreamEvent":
        event = getattr(message, "event", {}) or {}
        return [
            Event(
                kind="stream_event",
                message=stream_event_text(event),
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                provider_parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
                raw=message,
            )
        ]
    if name == "HookEventMessage":
        return [
            Event(
                kind="hook",
                message=getattr(message, "hook_event_name", None),
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        ]
    if name == "RateLimitEvent":
        return [
            Event(
                kind="rate_limit",
                message="rate limit updated",
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        ]
    return [Event(kind=name, raw=message)]


def assistant_events(message: Any) -> list[Event]:
    events: list[Event] = []
    for block in getattr(message, "content", []):
        if type(block).__name__ == "TextBlock":
            events.append(
                Event(
                    kind="text",
                    message=getattr(block, "text", None),
                    provider_session_id=getattr(message, "session_id", None),
                    provider_event_id=first_text(
                        getattr(message, "uuid", None),
                        getattr(message, "message_id", None),
                    ),
                    provider_parent_tool_use_id=getattr(
                        message, "parent_tool_use_id", None
                    ),
                    raw=message,
                )
            )
    usage = claude_usage(getattr(message, "usage", None))
    if usage is not None:
        events.append(
            Event(
                kind="usage",
                message=usage_message(usage),
                usage=usage,
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=first_text(
                    getattr(message, "uuid", None),
                    getattr(message, "message_id", None),
                ),
                raw=message,
            )
        )
    return events or [Event(kind="assistant", raw=message)]


def result_events(message: Any) -> list[Event]:
    usage = claude_usage(getattr(message, "usage", None))
    events: list[Event] = []
    structured_output = getattr(message, "structured_output", None)
    result_text = getattr(message, "result", None)
    if structured_output is not None:
        events.append(
            Event(
                kind="text",
                message=str(structured_output),
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        )
    elif result_text:
        events.append(
            Event(
                kind="result",
                message=str(result_text),
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        )
    if usage is not None:
        events.append(
            Event(
                kind="usage",
                message=usage_message(usage),
                usage=usage,
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        )
    events.append(
        Event(
            kind="done",
            message=str(getattr(message, "subtype", "done")),
            provider_session_id=getattr(message, "session_id", None),
            provider_event_id=getattr(message, "uuid", None),
            raw=message,
        )
    )
    return events


def claude_usage(value: Any) -> Usage | None:
    if not isinstance(value, dict):
        return None
    input_tokens = int_field(value, "input_tokens")
    cached_input_tokens = first_int_field(
        value,
        "cached_input_tokens",
        "cache_read_input_tokens",
    )
    output_tokens = int_field(value, "output_tokens")
    total = sum(
        item
        for item in (input_tokens, cached_input_tokens, output_tokens)
        if item is not None
    )
    return Usage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total or None,
    )


def int_field(value: dict[str, Any], key: str) -> int | None:
    item = value.get(key)
    if isinstance(item, bool):
        return None
    if isinstance(item, int):
        return item
    if isinstance(item, float) and item.is_integer():
        return int(item)
    return None


def first_int_field(value: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        item = int_field(value, key)
        if item is not None:
            return item
    return None


def usage_message(usage: Usage) -> str:
    if usage.total_tokens is not None:
        return f"{usage.total_tokens} tokens"
    return "usage updated"


def stream_event_text(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None
    delta = event.get("delta")
    if isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            return text
    text = event.get("text")
    return text if isinstance(text, str) else None


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def system_prompt(agent: Agent, goal: Goal | None) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    skill_text = compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    if goal:
        parts.append(
            "Current goal:\n"
            f"{goal.objective}\n\n"
            "Work toward the goal, respect any budget, and stop when the goal is "
            "complete, blocked, or unsafe to continue."
        )
    return "\n\n".join(parts) or None


def compiled_skills(agent: Agent) -> str | None:
    skills = [
        skill
        for skill in agent.skills
        if skill.instructions and not is_plugin_skill_path(skill.path)
    ]
    if not skills:
        return None
    sections = [
        "Available Yoke skills follow. Treat each skill as optional procedure context; "
        "use it only when the user request matches its description."
    ]
    for skill in skills:
        header = skill.name or "skill"
        description = f"\nDescription: {skill.description}" if skill.description else ""
        sections.append(f"## {header}{description}\n\n{skill.instructions}")
    return "\n\n".join(sections)


def output_format(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    return {"type": "json_schema", "schema": schema}


def tools(agent: Agent) -> list[str] | None:
    names = claude_tools(agent)
    return names if names else None


def claude_tools(agent: Agent) -> list[str]:
    names: list[str] = []
    if agent.tools.read:
        names.extend(["Read", "Grep", "Glob"])
    if agent.tools.write:
        names.extend(["Write", "Edit"])
    if agent.tools.shell:
        names.append("Bash")
    if agent.tools.web:
        names.extend(["WebFetch", "WebSearch"])
    if agent.tools.agent:
        names.append("Agent")
    return names


def allowed_tools(
    agent: Agent, harness: Harness, override: Any | None = None
) -> list[str]:
    permissions = override or harness.permissions or agent.permissions
    if permissions.approval is not Approval.AUTO:
        return []
    return claude_tools(agent)


def disallowed_tools(agent: Agent) -> list[str]:
    names: list[str] = []
    if not agent.tools.read:
        names.extend(["Read", "Grep", "Glob"])
    if not agent.tools.write:
        names.extend(["Write", "Edit"])
    if not agent.tools.shell:
        names.append("Bash")
    if not agent.tools.web:
        names.extend(["WebFetch", "WebSearch"])
    if not agent.tools.agent:
        names.append("Agent")
    return names


def permission_mode(harness: Harness, override: Any | None = None) -> str | None:
    return permission_mode_for_agent(harness.agent, override or harness.permissions)


def permission_mode_for_agent(agent: Agent, override: Any | None = None) -> str | None:
    permissions = override or agent.permissions
    if permissions.approval is Approval.NEVER:
        return "dontAsk"
    if permissions.approval is Approval.AUTO:
        if permissions.access is Access.FULL:
            return "bypassPermissions"
        if permissions.access is Access.WRITE:
            return "acceptEdits"
        return "default"
    return "default"


def skill_names(agent: Agent) -> list[str]:
    names: list[str] = []
    for skill in agent.skills:
        if skill.name:
            names.append(skill.name)
        elif skill.path:
            names.append(skill.path.stem)
    return names


def claude_plugins(agent: Agent) -> list[dict[str, str]]:
    return [
        {"type": "local", "path": str(path)}
        for path in plugin_paths(agent)
    ]
