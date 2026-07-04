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
)
from yoke.options import RunOptions, SessionOptions


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
            Feature.SKILLS: Support.NATIVE,
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
            yield Event(kind=type(message).__name__, raw=message)

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
        skills=skill_names(agent) or None,
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
    try:
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
    except ImportError as exc:
        raise YokeError("Claude support requires `pip install yoke[claude]`.") from exc

    events: list[Event] = []
    text: list[str] = []
    async for message in messages:
        events.append(Event(kind=type(message).__name__, raw=message))
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text.append(block.text)
        elif isinstance(message, ResultMessage) and message.structured_output:
            text.append(str(message.structured_output))
    return Run(
        provider=provider,
        output="\n".join(text).strip(),
        events=tuple(events),
        session=session,
    )


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
    skills = [skill for skill in agent.skills if skill.instructions]
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
