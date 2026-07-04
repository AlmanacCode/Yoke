"""Codex app-server adapter.

This surface is intentionally separate from the Codex CLI adapter. The app
server owns thread state, native mutable goals, and the richer notification
stream used by app integrations.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import signal
import subprocess
import threading
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeGuard

from pydantic import JsonValue, TypeAdapter, ValidationError

from yoke.capabilities import Capabilities, Feature, Support
from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Access,
    Approval,
    Event,
    Goal,
    GoalStatus,
    Harness,
    Provider,
    Run,
    Session,
    Turn,
)
from yoke.options import RunOptions, SessionOptions

JSON_VALUE = TypeAdapter(JsonValue)

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]


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
        return Run(
            provider=self.provider,
            output=result.output,
            events=tuple(result.events),
            session=session,
            usage=result.usage,
        )

    def _thread(self, session: Session) -> "AppServerThread":
        try:
            return self._threads[session.id]
        except KeyError as exc:
            raise YokeError(f"Codex app-server session is not live: {session.id}") from exc

    def _start_process(self, cwd: Path) -> "JsonRpcLineProcess":
        args = ["app-server"]
        for override in config_overrides(self.config):
            args.extend(["--config", override])
        args.extend(["--listen", "stdio://"])
        return JsonRpcLineProcess.start(self.executable, tuple(args), cwd, self.env)

    def _start_thread(
        self,
        process: "JsonRpcLineProcess",
        harness: Harness,
        options: SessionOptions,
        permissions: Any,
        goal: Goal | None,
    ) -> "AppServerThread":
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
        thread: "AppServerThread",
        session: Session,
        turn: Turn,
        output_schema: dict[str, Any] | None,
    ) -> "TurnResult":
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

    def _set_goal(self, thread: "AppServerThread", goal: Goal) -> Goal:
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

    def _clear_goal(self, thread: "AppServerThread") -> None:
        request_rpc(
            thread.process,
            "thread/goal/clear",
            {"threadId": thread.thread_id},
            self.rpc_timeout_seconds,
        )


@dataclass
class AppServerThread:
    process: "JsonRpcLineProcess"
    thread_id: str
    cwd: Path
    permissions: Any
    effort: Any | None


@dataclass
class TurnResult:
    output: str = ""
    events: list[Event] = field(default_factory=list)
    usage: dict[str, Any] | None = None


class JsonRpcLineProcess:
    """Line-oriented JSON-RPC process for Codex app-server."""

    def __init__(self, child: subprocess.Popen[str]) -> None:
        self.child = child
        self.messages: queue.Queue[dict[str, JsonValue] | ProcessStreamClosed] = (
            queue.Queue()
        )
        self.stderr_chunks: list[str] = []
        self._next_request_id = 1
        self._start_reader_threads()

    @classmethod
    def start(
        cls,
        command: str,
        args: tuple[str, ...],
        cwd: Path,
        env: dict[str, str] | None,
    ) -> "JsonRpcLineProcess":
        process_env = dict(os.environ)
        process_env.setdefault("YOKE_INTERNAL_SESSION", "1")
        if env is not None:
            process_env.update(env)
        child = subprocess.Popen(
            (command, *args),
            cwd=cwd,
            env=process_env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            start_new_session=True,
        )
        return cls(child)

    def next_request_id(self) -> int:
        value = self._next_request_id
        self._next_request_id += 1
        return value

    def write(self, message: Mapping[str, JsonValue]) -> None:
        if self.child.stdin is None:
            raise YokeError("Codex app-server stdin is closed")
        self.child.stdin.write(f"{json.dumps(message)}\n")
        self.child.stdin.flush()

    def read_until(self, deadline: float, timeout_label: str) -> dict[str, JsonValue]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise YokeError(f"Codex app-server {timeout_label}")
            if self.child.poll() is not None and self.messages.empty():
                raise YokeError(self.exit_message())
            try:
                item = self.messages.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                continue
            if isinstance(item, ProcessStreamClosed):
                if self.child.poll() is not None:
                    raise YokeError(self.exit_message())
                continue
            return item

    def terminate(self) -> None:
        if self.child.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.child.pid), signal.SIGTERM)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            self.child.terminate()
        try:
            self.child.wait(timeout=0.5)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(os.getpgid(self.child.pid), signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            self.child.kill()
        with suppress_timeout():
            self.child.wait(timeout=0.5)

    def exit_message(self) -> str:
        stderr = "".join(self.stderr_chunks).strip()
        first = stderr.splitlines()[0] if stderr else ""
        return first or f"codex app-server exited {self.child.returncode or 1}"

    def _start_reader_threads(self) -> None:
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        try:
            if self.child.stdout is None:
                return
            for line in self.child.stdout:
                message = parse_json_line(line)
                if message is not None:
                    self.messages.put(message)
        finally:
            self.messages.put(ProcessStreamClosed())

    def _read_stderr(self) -> None:
        if self.child.stderr is None:
            return
        for chunk in self.child.stderr:
            self.stderr_chunks.append(chunk)


@dataclass(frozen=True)
class ProcessStreamClosed:
    pass


def request_rpc(
    process: JsonRpcLineProcess,
    method: str,
    params: dict[str, JsonValue] | None,
    timeout_seconds: float,
) -> JsonValue:
    request_id = process.next_request_id()
    process.write({"id": request_id, "method": method, "params": params})
    deadline = time.monotonic() + timeout_seconds
    while True:
        message = process.read_until(deadline, f"{method} timed out")
        if is_server_request(message):
            respond_to_server_request(process, message)
            continue
        if "id" in message:
            if message.get("id") != request_id:
                continue
            error = as_record(message.get("error"))
            if error:
                detail = string_field(error, "message") or "request failed"
                raise YokeError(f"Codex app-server {method}: {detail}")
            return message.get("result")


def read_turn(
    process: JsonRpcLineProcess,
    thread_id: str,
    turn_id: str | None,
    timeout_seconds: float,
) -> TurnResult:
    result = TurnResult()
    deadline = time.monotonic() + timeout_seconds
    while True:
        message = process.read_until(deadline, "turn timed out")
        if is_server_request(message):
            respond_to_server_request(process, message)
            continue
        method = string_field(message, "method")
        if method is None:
            continue
        mapped = map_notification(message, result)
        result.events.extend(mapped)
        if method == "error":
            detail = result.output or "Codex app-server error"
            raise YokeError(detail)
        if method == "turn/completed" and is_root_turn(message, thread_id, turn_id):
            error = turn_error(message)
            if error:
                raise YokeError(error)
            result.events.append(Event(kind="done", message="codex completed"))
            return result


def respond_to_server_request(
    process: JsonRpcLineProcess,
    message: dict[str, JsonValue],
) -> None:
    request_id = message.get("id")
    method = string_field(message, "method")
    if request_id is None or method is None:
        return
    response = noninteractive_response(method)
    if response.error is not None:
        process.write({"id": request_id, "error": response.error})
        return
    process.write({"id": request_id, "result": response.result})


def map_notification(
    notification: dict[str, JsonValue],
    result: TurnResult,
) -> list[Event]:
    method = string_field(notification, "method")
    params = as_record(notification.get("params"))
    if method == "item/agentMessage/delta":
        delta = string_field(params, "delta")
        return [Event(kind="text_delta", message=delta, raw=notification)] if delta else []
    if method in {"item/plan/delta", "item/commandExecution/outputDelta"}:
        delta = string_field(params, "delta") or string_field(params, "deltaBase64")
        return [Event(kind="tool_summary", message=delta, raw=notification)] if delta else []
    if method == "turn/plan/updated":
        summary = plan_summary(params)
        return (
            [Event(kind="tool_summary", message=summary, raw=notification)]
            if summary
            else []
        )
    if method == "thread/tokenUsage/updated":
        usage = as_record(params.get("tokenUsage"))
        result.usage = usage or None
        return [Event(kind="context_usage", message="usage updated", raw=notification)]
    if method == "item/started":
        item = as_record(params.get("item"))
        return [Event(kind="tool_use", message=item_title(item), raw=notification)]
    if method == "item/completed":
        item = as_record(params.get("item"))
        if string_field(item, "type") == "agentMessage":
            text = string_field(item, "text")
            if text:
                result.output = text
                return [Event(kind="text", message=text, raw=notification)]
            return []
        return [Event(kind="tool_result", message=item_title(item), raw=notification)]
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
        return [Event(kind="warning", message=message, raw=notification)]
    if method == "error":
        error = as_record(params.get("error"))
        message = string_field(error, "message") or string_field(params, "message")
        result.output = message or "Codex app-server error"
        return [Event(kind="error", message=result.output, raw=notification)]
    return []


@dataclass(frozen=True)
class ServerResponse:
    result: dict[str, JsonValue] | None = None
    error: dict[str, JsonValue] | None = None


def noninteractive_response(method: str) -> ServerResponse:
    if method in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
    }:
        return ServerResponse(result={"decision": "decline"})
    if method in {"execCommandApproval", "applyPatchApproval"}:
        return ServerResponse(result={"decision": "denied"})
    if method == "item/tool/requestUserInput":
        return ServerResponse(result={"answers": {}})
    if method == "mcpServer/elicitation/request":
        return ServerResponse(result={"action": "decline", "content": None})
    if method == "item/tool/call":
        return ServerResponse(result={"contentItems": [], "success": False})
    if method == "item/permissions/requestApproval":
        return ServerResponse(
            result={"permissions": {}, "scope": "turn", "strictAutoReview": True}
        )
    return ServerResponse(
        error={
            "code": -32601,
            "message": f"Yoke does not handle Codex app-server request {method}",
        }
    )


def developer_instructions(agent: Any) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    skill_text = compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    return "\n\n".join(parts) or None


def compiled_skills(agent: Any) -> str | None:
    skills = [skill for skill in agent.skills if skill.instructions]
    if not skills:
        return None
    sections = [
        "Available Yoke skills follow. Treat each skill as optional procedure "
        "context; use it only when the user request matches its description."
    ]
    for skill in skills:
        header = skill.name or "skill"
        description = f"\nDescription: {skill.description}" if skill.description else ""
        sections.append(f"## {header}{description}\n\n{skill.instructions}")
    return "\n\n".join(sections)


def sandbox_mode(permissions: Any) -> SandboxMode:
    access = permissions.access
    if access is Access.FULL or str(access).endswith("full"):
        return "danger-full-access"
    if access is Access.WRITE or str(access).endswith("write"):
        return "workspace-write"
    return "read-only"


def sandbox_policy(cwd: Path, mode: SandboxMode) -> dict[str, JsonValue]:
    if mode == "danger-full-access":
        return {"type": "dangerFullAccess"}
    if mode == "read-only":
        return {"type": "readOnly"}
    return {
        "type": "workspaceWrite",
        "writableRoots": [str(cwd)],
        "networkAccess": False,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def approval_policy(permissions: Any) -> str:
    approval = permissions.approval
    if approval is Approval.AUTO or str(approval).endswith("auto"):
        return "on-failure"
    if approval is Approval.ASK or str(approval).endswith("ask"):
        return "on-request"
    return "never"


def app_goal_status(status: GoalStatus) -> str:
    mapping = {
        GoalStatus.ACTIVE: "active",
        GoalStatus.PAUSED: "paused",
        GoalStatus.BLOCKED: "blocked",
        GoalStatus.USAGE_LIMITED: "usageLimited",
        GoalStatus.BUDGET_LIMITED: "budgetLimited",
        GoalStatus.COMPLETE: "complete",
    }
    return mapping[status]


def yoke_goal(value: dict[str, JsonValue]) -> Goal | None:
    objective = string_field(value, "objective")
    if objective is None:
        return None
    return Goal(
        objective,
        status=yoke_goal_status(string_field(value, "status")),
        token_budget=number_field(value, "tokenBudget"),
        tokens_used=number_field(value, "tokensUsed"),
        time_used_seconds=number_field(value, "timeUsedSeconds"),
    )


def yoke_goal_status(value: str | None) -> GoalStatus:
    mapping = {
        "active": GoalStatus.ACTIVE,
        "paused": GoalStatus.PAUSED,
        "blocked": GoalStatus.BLOCKED,
        "usageLimited": GoalStatus.USAGE_LIMITED,
        "budgetLimited": GoalStatus.BUDGET_LIMITED,
        "complete": GoalStatus.COMPLETE,
    }
    return mapping.get(value or "", GoalStatus.ACTIVE)


def is_root_turn(
    notification: dict[str, JsonValue],
    thread_id: str,
    turn_id: str | None,
) -> bool:
    if string_field(notification, "method") != "turn/completed":
        return False
    params = as_record(notification.get("params"))
    completed_turn_id = string_field(params, "turnId")
    completed_thread_id = string_field(params, "threadId")
    return completed_turn_id == turn_id or completed_thread_id == thread_id


def turn_error(notification: dict[str, JsonValue]) -> str | None:
    params = as_record(notification.get("params"))
    turn = as_record(params.get("turn"))
    error = as_record(turn.get("error"))
    return string_field(error, "message")


def plan_summary(params: dict[str, JsonValue]) -> str | None:
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


def item_title(item: dict[str, JsonValue]) -> str:
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


def parse_json_line(line: str) -> dict[str, JsonValue] | None:
    stripped = line.strip()
    if stripped == "":
        return None
    try:
        parsed = JSON_VALUE.validate_python(json.loads(stripped))
    except (json.JSONDecodeError, ValidationError, ValueError):
        return None
    record = as_record(parsed)
    return record or None


def is_server_request(message: dict[str, JsonValue]) -> bool:
    return "id" in message and string_field(message, "method") is not None


def as_record(value: JsonValue | None) -> dict[str, JsonValue]:
    if is_record(value):
        return value
    return {}


def is_record(value: JsonValue | None) -> TypeGuard[dict[str, JsonValue]]:
    return isinstance(value, dict)


def string_field(record: Mapping[str, JsonValue], field: str) -> str | None:
    value = record.get(field)
    if isinstance(value, str) and value != "":
        return value
    return None


def number_field(record: Mapping[str, JsonValue], field: str) -> int | None:
    value = record.get(field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


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


class suppress_timeout:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return isinstance(exc, subprocess.TimeoutExpired)
