"""Codex app-server adapter.

This surface is intentionally separate from the Codex CLI adapter. The app
server owns thread state, native mutable goals, and the richer notification
stream used by app integrations.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yoke.capabilities import Capabilities, Feature, Support
from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import Event, Goal, Harness, Provider, Run, Session, Turn
from yoke.options import RunOptions, SessionOptions
from yoke.providers.codex_app.events import TurnResult, read_turn
from yoke.providers.codex_app.fields import as_record, string_field
from yoke.providers.codex_app.goals import app_goal_status, yoke_goal
from yoke.providers.codex_app.policy import approval_policy, sandbox_mode, sandbox_policy
from yoke.providers.codex_app.process import JsonRpcLineProcess
from yoke.providers.codex_app.prompts import developer_instructions
from yoke.providers.codex_app.rpc import request_rpc


class CodexAppServer:
    """Adapter for `codex app-server --listen stdio://`."""

    provider: Provider = "codex"
    surface = "codex_app_server"
    capabilities = Capabilities.from_map(
        {
            Feature.ONE_SHOT: Support.NATIVE,
            Feature.SESSION: Support.NATIVE,
            Feature.STREAMING: (
                Support.EMULATED,
                "The protocol streams notifications; this adapter currently collects.",
            ),
            Feature.STRUCTURED_OUTPUT: Support.NATIVE,
            Feature.FILESYSTEM_AGENT: Support.UNSUPPORTED,
            Feature.INLINE_SUBAGENTS: (
                Support.NATIVE,
                "Codex app-server emits collab-agent activity from native tools.",
            ),
            Feature.DECLARED_SUBAGENTS: Support.UNSUPPORTED,
            Feature.SKILLS: (
                Support.NATIVE,
                "App-server has skills APIs; Yoke folder skill wiring is future work.",
            ),
            Feature.HOOKS: Support.NATIVE,
            Feature.MCP: Support.NATIVE,
            Feature.GOAL: Support.NATIVE,
            Feature.MUTABLE_GOAL: Support.NATIVE,
            Feature.WORKFLOW: Support.UNSUPPORTED,
        }
    )

    def __init__(
        self,
        executable: str = "codex",
        *,
        rpc_timeout_seconds: float = 30,
        turn_timeout_seconds: float = 30 * 60,
        ephemeral: bool = True,
        client_name: str = "yoke",
        client_title: str = "Yoke",
        client_version: str = "0.0.0",
        config: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.executable = executable
        self.rpc_timeout_seconds = rpc_timeout_seconds
        self.turn_timeout_seconds = turn_timeout_seconds
        self.ephemeral = ephemeral
        self.client_name = client_name
        self.client_title = client_title
        self.client_version = client_version
        self.config = config or {"mcp_servers": {}}
        self.env = env
        self._threads: dict[str, AppServerThread] = {}

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        session = await self.start(
            harness,
            SessionOptions(
                goal=options.goal,
                effort=options.effort,
                permissions=options.permissions,
                provider=options.provider,
            ),
        )
        try:
            return await self._send(
                session,
                Turn(prompt=prompt),
                output_schema=options.output_schema,
            )
        finally:
            await self.close(session)

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        if options.resume:
            raise UnsupportedFeature(
                "codex_app_server resume needs thread/read support before Yoke "
                "can attach to existing app-server threads."
            )
        permissions = options.permissions or harness.permissions or harness.agent.permissions
        process = await asyncio.to_thread(self._start_process, harness.cwd)
        goal = options.goal or harness.agent.goal
        try:
            thread = await asyncio.to_thread(
                self._start_thread,
                process,
                harness,
                options,
                permissions,
                goal,
            )
        except Exception:
            process.terminate()
            raise
        self._threads[thread.thread_id] = thread
        session = Session(
            provider=self.provider,
            surface=self.surface,
            id=thread.thread_id,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=None,
        )
        if goal is not None:
            session = await self.set_goal(session, goal)
        return session

    async def send(self, session: Session, turn: Turn) -> Run:
        return await self._send(session, turn, output_schema=None)

    async def stream(self, session: Session, turn: Turn) -> AsyncIterator[Event]:
        run = await self.send(session, turn)
        for event in run.events:
            yield event

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        thread = self._thread(session)
        updated = await asyncio.to_thread(self._set_goal, thread, goal)
        return session.model_copy(update={"goal": updated})

    async def clear_goal(self, session: Session) -> Session:
        thread = self._thread(session)
        await asyncio.to_thread(self._clear_goal, thread)
        return session.model_copy(update={"goal": None})

    async def close(self, session: Session) -> None:
        thread = self._threads.pop(session.id, None)
        if thread is not None:
            await asyncio.to_thread(thread.process.terminate)

    async def _send(
        self,
        session: Session,
        turn: Turn,
        *,
        output_schema: dict[str, Any] | None,
    ) -> Run:
        thread = self._thread(session)
        result = await asyncio.to_thread(
            self._run_turn,
            thread,
            session,
            turn,
            output_schema,
        )
        result.events.insert(
            0,
            Event(
                kind="provider_session",
                message=f"codex provider session {thread.thread_id}",
                provider_session_id=thread.thread_id,
            ),
        )
        return Run(
            provider=self.provider,
            output=result.output,
            events=tuple(result.events),
            session=session,
            usage=result.usage,
        )

    def _thread(self, session: Session) -> AppServerThread:
        try:
            return self._threads[session.id]
        except KeyError as exc:
            raise YokeError(f"Codex app-server session is not live: {session.id}") from exc

    def _start_process(self, cwd: Path) -> JsonRpcLineProcess:
        args = ["app-server"]
        for override in config_overrides(self.config):
            args.extend(["--config", override])
        args.extend(["--listen", "stdio://"])
        return JsonRpcLineProcess.start(self.executable, tuple(args), cwd, self.env)

    def _start_thread(
        self,
        process: JsonRpcLineProcess,
        harness: Harness,
        options: SessionOptions,
        permissions: Any,
        goal: Goal | None,
    ) -> AppServerThread:
        request_rpc(
            process,
            "initialize",
            {
                "clientInfo": {
                    "name": self.client_name,
                    "title": self.client_title,
                    "version": self.client_version,
                },
                "capabilities": {"experimentalApi": True},
            },
            self.rpc_timeout_seconds,
        )
        response = as_record(
            request_rpc(
                process,
                "thread/start",
                {
                    "cwd": str(harness.cwd),
                    "model": harness.agent.model,
                    "approvalPolicy": approval_policy(permissions),
                    "sandbox": sandbox_mode(permissions),
                    "developerInstructions": developer_instructions(harness.agent),
                    "ephemeral": self.ephemeral if goal is None else False,
                },
                self.rpc_timeout_seconds,
            )
        )
        thread_id = string_field(as_record(response.get("thread")), "id")
        if thread_id is None:
            raise YokeError("Codex app-server thread/start did not return a thread id")
        return AppServerThread(
            process=process,
            thread_id=thread_id,
            cwd=harness.cwd,
            permissions=permissions,
            effort=options.effort or harness.agent.effort,
        )

    def _run_turn(
        self,
        thread: AppServerThread,
        session: Session,
        turn: Turn,
        output_schema: dict[str, Any] | None,
    ) -> TurnResult:
        response = as_record(
            request_rpc(
                thread.process,
                "turn/start",
                {
                    "threadId": thread.thread_id,
                    "cwd": str(thread.cwd),
                    "input": [
                        {
                            "type": "text",
                            "text": turn.prompt,
                            "text_elements": [],
                        }
                    ],
                    "approvalPolicy": approval_policy(
                        session.permissions or thread.permissions
                    ),
                    "sandboxPolicy": sandbox_policy(
                        thread.cwd,
                        sandbox_mode(session.permissions or thread.permissions),
                    ),
                    "model": session.agent.model if session.agent else None,
                    "effort": str(thread.effort) if thread.effort else None,
                    "outputSchema": output_schema,
                },
                self.rpc_timeout_seconds,
            )
        )
        turn_id = string_field(as_record(response.get("turn")), "id")
        return read_turn(
            thread.process,
            thread.thread_id,
            turn_id,
            self.turn_timeout_seconds,
        )

    def _set_goal(self, thread: AppServerThread, goal: Goal) -> Goal:
        response = as_record(
            request_rpc(
                thread.process,
                "thread/goal/set",
                {
                    "threadId": thread.thread_id,
                    "objective": goal.objective,
                    "status": app_goal_status(goal.status),
                    "tokenBudget": goal.token_budget,
                },
                self.rpc_timeout_seconds,
            )
        )
        return yoke_goal(as_record(response.get("goal"))) or goal

    def _clear_goal(self, thread: AppServerThread) -> None:
        request_rpc(
            thread.process,
            "thread/goal/clear",
            {"threadId": thread.thread_id},
            self.rpc_timeout_seconds,
        )


@dataclass
class AppServerThread:
    process: JsonRpcLineProcess
    thread_id: str
    cwd: Path
    permissions: Any
    effort: Any | None


def config_overrides(config: dict[str, Any]) -> list[str]:
    overrides: list[str] = []
    flatten_config(config, "", overrides)
    return overrides


def flatten_config(value: Any, prefix: str, overrides: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flatten_config(child, path, overrides)
        return
    if not prefix:
        raise ValueError("Codex app-server config overrides must be keyed")
    overrides.append(f"{prefix}={json.dumps(value)}")
