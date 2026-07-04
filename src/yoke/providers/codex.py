"""Codex CLI adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yoke.capabilities import Capabilities, Feature, Support
from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import Event, Goal, Harness, Provider, Run, Session, Turn
from yoke.options import RunOptions, SessionOptions
from yoke.providers.codex_cli import CodexCli


class Codex:
    """Adapter for Codex CLI JSONL execution."""

    provider: Provider = "codex"
    surface = "codex_cli"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: (
                Support.COMPILED,
                "codex_cli sessions are resumable exec threads, not live processes.",
            ),
            Feature.STREAMING: (
                Support.NATIVE,
                "codex exec emits JSONL events for each turn.",
            ),
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.FILESYSTEM_AGENT: Support.UNSUPPORTED,
            Feature.INLINE_SUBAGENTS: Support.UNSUPPORTED,
            Feature.DECLARED_SUBAGENTS: Support.UNSUPPORTED,
            Feature.SKILLS: Support.UNSUPPORTED,
            Feature.HOOKS: Support.UNSUPPORTED,
            Feature.MCP: Support.UNSUPPORTED,
            Feature.GOAL: (
                Support.COMPILED,
                "CLI runs receive goals in the prompt; app-server owns native mutable goals.",
            ),
            Feature.MUTABLE_GOAL: Support.UNSUPPORTED,
            Feature.WORKFLOW: Support.UNSUPPORTED,
        }
    )

    def __init__(
        self,
        executable: str = "codex",
        env: dict[str, str] | None = None,
        config: dict[str, Any] | None = None,
        skip_git_repo_check: bool = False,
        additional_directories: tuple[str | Path, ...] = (),
    ) -> None:
        self.cli = CodexCli(executable=executable, env=env, config=config)
        self.skip_git_repo_check = skip_git_repo_check
        self.additional_directories = tuple(Path(path) for path in additional_directories)

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        agent = harness.agent
        permissions = options.permissions or harness.permissions or agent.permissions
        return await self._run_turn(
            prompt=prompt,
            agent=agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=options.goal or agent.goal,
            effort=options.effort or agent.effort,
            output_schema=options.output_schema,
            thread_id=None,
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        if not options.resume:
            raise UnsupportedFeature(
                "codex_cli sessions begin after run(); pass Run.session or resume an id."
            )
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=options.resume,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=options.permissions or harness.permissions or harness.agent.permissions,
            goal=options.goal or harness.agent.goal,
        )

    async def send(self, session: Session, turn: Turn) -> Run:
        if session.agent is None or session.cwd is None:
            raise YokeError("Codex CLI session needs agent and cwd to resume.")
        return await self._run_turn(
            prompt=turn.prompt,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions or session.agent.permissions,
            goal=session.goal,
            effort=session.agent.effort,
            output_schema=None,
            thread_id=session.id,
        )

    async def stream(self, session: Session, turn: Turn):
        if session.agent is None or session.cwd is None:
            raise YokeError("Codex CLI session needs agent and cwd to resume.")
        async for event in self.cli.run(
            prompt=codex_prompt(turn.prompt, session.goal, session.agent),
            cwd=session.cwd,
            thread_id=session.id,
            model=session.agent.model,
            sandbox=sandbox_mode(session.permissions or session.agent.permissions),
            approval=approval_policy(session.permissions or session.agent.permissions),
            effort=str(session.agent.effort) if session.agent.effort else None,
            network=(session.permissions or session.agent.permissions).network,
            web_search="live" if session.agent.tools.web else "disabled",
            skip_git_repo_check=self.skip_git_repo_check,
            additional_directories=self.additional_directories,
        ):
            yield Event(kind=str(event.get("type", "unknown")), raw=event)

    async def _run_turn(
        self,
        *,
        prompt: str,
        agent: Any,
        cwd: Path,
        permissions: Any,
        goal: Goal | None,
        effort: Any | None,
        output_schema: dict[str, Any] | None,
        thread_id: str | None,
    ) -> Run:
        events: list[Event] = []
        output = ""
        usage: dict[str, Any] | None = None
        session: Session | None = None

        async for event in self.cli.run(
            prompt=codex_prompt(prompt, goal, agent),
            cwd=cwd,
            thread_id=thread_id,
            model=agent.model,
            sandbox=sandbox_mode(permissions),
            approval=approval_policy(permissions),
            effort=str(effort) if effort else None,
            network=permissions.network,
            web_search="live" if agent.tools.web else "disabled",
            output_schema=output_schema,
            skip_git_repo_check=self.skip_git_repo_check,
            additional_directories=self.additional_directories,
        ):
            events.append(Event(kind=str(event.get("type", "unknown")), raw=event))
            if event.get("type") == "thread.started":
                session = Session(
                    provider=self.provider,
                    surface=self.surface,
                    id=str(event["thread_id"]),
                    agent=agent,
                    cwd=cwd,
                    permissions=permissions,
                    goal=goal,
                )
            elif event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    output = str(item.get("text", ""))
            elif event.get("type") == "turn.completed":
                usage = event.get("usage")
            elif event.get("type") == "turn.failed":
                error = event.get("error", {})
                raise YokeError(str(error.get("message", "Codex turn failed")))
            elif event.get("type") == "error":
                raise YokeError(str(event.get("message", "Codex stream error")))

        return Run(
            provider=self.provider,
            output=output,
            events=tuple(events),
            session=session,
            usage=usage,
        )

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def close(self, session: Session) -> None:
        return None


def codex_prompt(prompt: str, goal: Goal | None, agent: Any | None = None) -> str:
    parts: list[str] = []
    if agent is not None:
        skill_text = compiled_skills(agent)
        if skill_text:
            parts.append(skill_text)
    if goal is not None:
        parts.append(
            f"Goal: {goal.objective}\n\n"
            "Work toward this goal and stop when it is complete, blocked, or unsafe "
            "to continue."
        )
    parts.append(f"User request:\n{prompt}")
    return "\n\n".join(parts)


def compiled_skills(agent: Any) -> str | None:
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


def sandbox_mode(permissions: Any) -> str:
    access = str(permissions.access)
    if access.endswith("full"):
        return "danger-full-access"
    if access.endswith("write"):
        return "workspace-write"
    return "read-only"


def approval_policy(permissions: Any) -> str:
    approval = str(permissions.approval)
    if approval.endswith("auto"):
        return "on-failure"
    if approval.endswith("ask"):
        return "on-request"
    return "never"
