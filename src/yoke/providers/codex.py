"""Codex CLI adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Authentication,
    AuthMethod,
    Event,
    Failure,
    Goal,
    GoalRun,
    Harness,
    Login,
    Provider,
    Readiness,
    Run,
    RunStatus,
    Session,
    Turn,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    ForkOptions,
    GoalLoopOptions,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
)
from yoke.providers.codex_cli import CodexCli
from yoke.providers.compiled import compiled_subagents
from yoke.readiness import run_command
from yoke.structured import OutputSchema, parse_output, provider_schema
from yoke.surfaces import capabilities_for
from yoke.workflows import native_workflow_unsupported


class Codex:
    """Adapter for Codex CLI JSONL execution."""

    provider: Provider = "codex"
    surface = "codex_cli"
    capabilities = capabilities_for(provider, surface)

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
        self.additional_directories = tuple(
            Path(path) for path in additional_directories
        )

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        agent = harness.agent
        permissions = options.permissions or harness.permissions or agent.permissions
        return await self._run_turn(
            prompt=prompt,
            agent=agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=options.resolve_goal(agent.goal),
            effort=options.effort or agent.effort,
            model=options.model or agent.model,
            output_schema=options.output_schema,
            thread_id=None,
        )

    async def check(self, harness: Harness) -> Readiness:
        try:
            result = await run_command(
                self.cli.executable,
                "login",
                "status",
                env=self.cli.env,
            )
        except FileNotFoundError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex not found on PATH",
                fix="Install Codex or pass a Codex adapter with the executable path.",
            )
        except TimeoutError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex login status timed out",
            )
        if result.code != 0:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=result.message or f"codex login status exited {result.code}",
                raw=result.stderr or result.stdout,
            )
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=True,
            message=result.message or "codex authenticated",
        )

    async def auth_status(self, harness: Harness) -> Authentication:
        """Distinguish an installed CLI from an authenticated CLI."""

        readiness = await self.check(harness)
        installed = readiness.message != "codex not found on PATH"
        return Authentication(
            provider=self.provider,
            surface=self.surface,
            methods=(AuthMethod.EXTERNAL,),
            method=AuthMethod.EXTERNAL if readiness.available else None,
            installed=installed,
            authenticated=readiness.available if installed else None,
            compatible=None,
            ready=readiness.available,
            message=readiness.message,
        )

    async def login(
        self,
        harness: Harness,
        method: str,
        *,
        api_key: str | None = None,
    ) -> Login:
        raise UnsupportedFeature(
            "Codex CLI login is an external interactive flow; run `codex login` "
            "or use the codex_python_sdk surface for programmatic login."
        )

    async def models(self, harness: Harness):
        raise UnsupportedFeature(
            "Codex CLI model listing requires a different surface."
        )

    async def workflow(
        self,
        harness: Harness,
        workflow: Workflow,
        prompt: str,
        options: WorkflowOptions,
    ) -> WorkflowRun:
        raise native_workflow_unsupported(
            harness,
            workflow,
            options,
            reason=(
                "Codex CLI does not expose a public provider-native workflow "
                "adapter; use portable workflows, subagents, or goal mode."
            ),
        )

    async def goal_loop(
        self,
        harness: Harness,
        options: GoalLoopOptions,
    ) -> GoalRun:
        raise UnsupportedFeature(
            "Codex CLI documents /goal, but Yoke does not control the "
            "interactive CLI goal loop as a programmatic SDK operation. Use "
            "codex_app_server for a Yoke-managed goal-loop handle."
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        if not options.resume:
            raise UnsupportedFeature(
                "codex_cli sessions begin after run(); pass Run.session or "
                "resume an id."
            )
        permissions = (
            options.permissions or harness.permissions or harness.agent.permissions
        )
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=options.resume,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=options.resolve_goal(harness.agent.goal),
            model=options.model or harness.agent.model,
        )

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        if session.agent is None or session.cwd is None:
            raise YokeError("Codex CLI session needs agent and cwd to resume.")
        permissions = (
            options.permissions or session.permissions or session.agent.permissions
        )
        return await self._run_turn(
            prompt=turn.prompt,
            agent=session.agent,
            cwd=session.cwd,
            permissions=permissions,
            goal=options.resolve_goal(session.goal),
            effort=options.effort or session.agent.effort,
            model=options.model or session.model or session.agent.model,
            output_schema=options.output_schema,
            thread_id=session.id,
        )

    async def stream(self, session: Session, turn: Turn, options: RunOptions):
        if session.agent is None or session.cwd is None:
            raise YokeError("Codex CLI session needs agent and cwd to resume.")
        permissions = (
            options.permissions or session.permissions or session.agent.permissions
        )
        async for event in self.cli.run(
            prompt=codex_prompt(
                turn.prompt,
                options.resolve_goal(session.goal),
                session.agent,
            ),
            cwd=session.cwd,
            thread_id=session.id,
            model=options.model or session.model or session.agent.model,
            sandbox=sandbox_mode(permissions),
            approval=approval_policy(permissions),
            effort=str(options.effort or session.agent.effort)
            if options.effort or session.agent.effort
            else None,
            network=permissions.network,
            web_search="live" if session.agent.tools.web else "disabled",
            skip_git_repo_check=self.skip_git_repo_check,
            additional_directories=self.additional_directories,
        ):
            yield Event(
                kind=str(event.get("type", "unknown")),
                surface=self.surface,
                raw=event,
            )

    async def _run_turn(
        self,
        *,
        prompt: str,
        agent: Any,
        cwd: Path,
        permissions: Any,
        goal: Goal | None,
        effort: Any | None,
        model: str | None,
        output_schema: OutputSchema | None,
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
            model=model,
            sandbox=sandbox_mode(permissions),
            approval=approval_policy(permissions),
            effort=str(effort) if effort else None,
            network=permissions.network,
            web_search="live" if agent.tools.web else "disabled",
            output_schema=provider_schema(output_schema),
            skip_git_repo_check=self.skip_git_repo_check,
            additional_directories=self.additional_directories,
        ):
            events.append(
                Event(
                    kind=str(event.get("type", "unknown")),
                    surface=self.surface,
                    raw=event,
                )
            )
            if event.get("type") == "thread.started":
                session = Session(
                    provider=self.provider,
                    surface=self.surface,
                    id=str(event["thread_id"]),
                    agent=agent,
                    cwd=cwd,
                    permissions=permissions,
                    goal=goal,
                    model=model,
                )
            elif event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message":
                    output = str(item.get("text", ""))
            elif event.get("type") == "turn.completed":
                usage = event.get("usage")
            elif event.get("type") == "turn.failed":
                error = event.get("error", {})
                message = str(error.get("message", "Codex turn failed"))
                events.append(
                    Event(
                        kind="error",
                        surface=self.surface,
                        message=message,
                        raw=event,
                    )
                )
                return Run(
                    provider=self.provider,
                    surface=self.surface,
                    status=RunStatus.FAILED,
                    output=message,
                    events=tuple(events),
                    session=session,
                    usage=usage,
                    failure=Failure(message=message),
                    requested_model=model,
                )
            elif event.get("type") == "error":
                message = str(event.get("message", "Codex stream error"))
                events.append(
                    Event(
                        kind="error",
                        surface=self.surface,
                        message=message,
                        raw=event,
                    )
                )
                return Run(
                    provider=self.provider,
                    surface=self.surface,
                    status=RunStatus.FAILED,
                    output=message,
                    events=tuple(events),
                    session=session,
                    usage=usage,
                    failure=Failure(message=message),
                    requested_model=model,
                )

        structured = parse_output(output, output_schema)
        return Run(
            provider=self.provider,
            surface=self.surface,
            status=RunStatus.FAILED if structured.failure else RunStatus.SUCCEEDED,
            output=output,
            data=structured.data,
            events=tuple(events),
            session=session,
            usage=usage,
            failure=structured.failure,
            requested_model=model,
        )

    async def get_goal(self, session: Session) -> Goal | None:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def interrupt(self, session: Session) -> None:
        raise UnsupportedFeature("Codex CLI does not expose a live turn interrupt.")

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        raise UnsupportedFeature("Codex CLI does not expose native session forking.")

    async def close(self, session: Session) -> None:
        return None


def codex_prompt(prompt: str, goal: Goal | None, agent: Any | None = None) -> str:
    parts: list[str] = []
    if agent is not None:
        if agent.instructions:
            parts.append(agent.instructions)
        subagent_text = compiled_subagents(agent)
        if subagent_text:
            parts.append(subagent_text)
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
