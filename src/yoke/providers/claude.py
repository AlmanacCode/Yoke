"""Claude Agent SDK adapter."""

from __future__ import annotations

from typing import Any

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

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        """Execute a one-shot Claude run."""

        try:
            from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions
            from claude_agent_sdk import AgentDefinition as ClaudeAgentDefinition
            from claude_agent_sdk import ResultMessage, TextBlock, query
        except ImportError as exc:
            raise YokeError(
                "Claude support requires `pip install yoke[claude]`."
            ) from exc

        agent = harness.agent
        goal = options.goal or agent.goal
        claude_options = ClaudeAgentOptions(
            system_prompt=system_prompt(agent, goal),
            cwd=harness.cwd,
            model=agent.model,
            effort=options.effort or agent.effort,
            max_turns=options.max_turns,
            permission_mode=permission_mode(harness),
            tools=tools(agent),
            allowed_tools=allowed_tools(agent, harness),
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

        events: list[Event] = []
        text: list[str] = []
        async for message in query(prompt=prompt, options=claude_options):
            events.append(Event(kind=type(message).__name__, raw=message))
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text.append(block.text)
            elif isinstance(message, ResultMessage) and message.structured_output:
                text.append(str(message.structured_output))

        return Run(provider=self.provider, output="\n".join(text).strip(), events=tuple(events))

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        """Start a Claude session.

        Yoke has not landed the live-client ownership model yet, so this is
        intentionally not faked.
        """

        raise UnsupportedFeature(
            "Claude one-shot runs are implemented; live sessions need the next slice."
        )

    async def send(self, session: Session, turn: Turn) -> Run:
        raise UnsupportedFeature("Claude live sessions need the next slice.")

    async def stream(self, session: Session, turn: Turn):
        raise UnsupportedFeature("Claude streaming needs the next slice.")
        yield

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")


def system_prompt(agent: Agent, goal: Goal | None) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    if goal:
        parts.append(
            "Current goal:\n"
            f"{goal.objective}\n\n"
            "Work toward the goal, respect any budget, and stop when the goal is "
            "complete, blocked, or unsafe to continue."
        )
    return "\n\n".join(parts) or None


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


def allowed_tools(agent: Agent, harness: Harness) -> list[str]:
    permissions = harness.permissions or agent.permissions
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


def permission_mode(harness: Harness) -> str | None:
    return permission_mode_for_agent(harness.agent, harness.permissions)


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
