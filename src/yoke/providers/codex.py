"""Codex CLI adapter."""

from __future__ import annotations

from yoke.capabilities import Capabilities, Feature, Support
from pathlib import Path
from typing import Any

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
                Support.UNSUPPORTED,
                "codex exec can resume threads, but Yoke has not exposed live sessions yet.",
            ),
            Feature.STREAMING: (
                Support.UNSUPPORTED,
                "codex exec emits JSONL, but this adapter currently buffers run().",
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
        events: list[Event] = []
        output = ""
        usage: dict[str, Any] | None = None
        session: Session | None = None
        agent = harness.agent
        permissions = options.permissions or harness.permissions or agent.permissions

        async for event in self.cli.run(
            prompt=codex_prompt(prompt, options.goal or agent.goal),
            cwd=harness.cwd,
            model=agent.model,
            sandbox=sandbox_mode(permissions),
            approval=approval_policy(permissions),
            effort=str(options.effort or agent.effort)
            if (options.effort or agent.effort)
            else None,
            network=permissions.network,
            web_search="live" if agent.tools.web else "disabled",
            output_schema=options.output_schema,
            skip_git_repo_check=self.skip_git_repo_check,
            additional_directories=self.additional_directories,
        ):
            events.append(Event(kind=str(event.get("type", "unknown")), raw=event))
            if event.get("type") == "thread.started":
                session = Session(provider=self.provider, id=str(event["thread_id"]))
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

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        raise UnsupportedFeature("Codex start() needs a live-thread handle slice.")

    async def send(self, session: Session, turn: Turn) -> Run:
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")

    async def stream(self, session: Session, turn: Turn):
        raise UnsupportedFeature("Codex Python bridge is the next provider slice.")
        yield Event(kind="unreachable")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Codex mutable goals require app-server protocol.")


def codex_prompt(prompt: str, goal: Goal | None) -> str:
    if goal is None:
        return prompt
    return (
        f"Goal: {goal.objective}\n\n"
        "Work toward this goal and stop when it is complete, blocked, or unsafe "
        "to continue.\n\n"
        f"User request:\n{prompt}"
    )


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
