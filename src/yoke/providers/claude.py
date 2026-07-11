"""Claude Agent SDK adapter."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from yoke.errors import UnsupportedFeature, YokeError
from yoke.models import (
    Access,
    Agent,
    AgentCall,
    Approval,
    Authentication,
    AuthMethod,
    Event,
    EventKind,
    Failure,
    Goal,
    GoalRun,
    Harness,
    Login,
    Provider,
    Readiness,
    Request,
    RequestKind,
    Response,
    Run,
    RunStatus,
    Session,
    SessionHistory,
    SessionList,
    SessionMessage,
    SessionSummary,
    Tool,
    ToolKind,
    ToolStatus,
    Turn,
    Usage,
    Workflow,
    WorkflowRun,
)
from yoke.options import (
    ClaudeAgentOptions,
    ClaudeOptions,
    ClaudePermissionMode,
    ClaudeToolset,
    ForkOptions,
    GoalLoopOptions,
    Hook,
    RunOptions,
    SessionOptions,
    WorkflowOptions,
)
from yoke.providers.claude_plugins import (
    is_plugin_skill_path,
    plugin_paths,
    plugin_root_for_skill,
)
from yoke.readiness import run_command
from yoke.structured import OutputSchema, provider_schema
from yoke.surfaces import capabilities_for
from yoke.workflows import native_workflow_unsupported

ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
CLAUDE_CODE_OAUTH_TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
CLAUDE_INSTALL = "pip install almanac-yoke[claude]"


class Claude:
    """Adapter for Claude Agent SDK."""

    provider: Provider = "claude"
    surface = "claude_python_sdk"
    capabilities = capabilities_for(provider, surface)

    def __init__(
        self,
        executable: str = "claude",
        env: dict[str, str] | None = None,
    ) -> None:
        self.executable = executable
        self.env = env
        self._sessions: dict[str, ClaudeSession] = {}

    async def check(self, harness: Harness) -> Readiness:
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="claude_agent_sdk is not installed",
                fix=f"Install Claude support with `{CLAUDE_INSTALL}`.",
            )
        env = credential_env(harness, self.env)
        if env.get(ANTHROPIC_API_KEY, ""):
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=True,
                message=f"{ANTHROPIC_API_KEY} set",
            )
        try:
            result = await run_command(
                self.executable,
                "auth",
                "status",
                env=env,
            )
        except FileNotFoundError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="claude not found on PATH",
                fix="Install Claude Code or set ANTHROPIC_API_KEY.",
            )
        except TimeoutError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="claude auth status timed out",
            )
        if result.code != 0:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=result.message or f"claude auth status exited {result.code}",
                raw=result.stderr or result.stdout,
            )
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=True,
            message=claude_auth_status_message(result.stdout)
            or result.message
            or "claude authenticated",
        )

    async def auth_status(self, harness: Harness) -> Authentication:
        readiness = await self.check(harness)
        method = harness.credentials.method
        direct = method in (AuthMethod.API_KEY, AuthMethod.OAUTH_TOKEN)
        return Authentication(
            provider=self.provider,
            surface=self.surface,
            methods=harness.auth_methods(),
            method=(
                method
                if direct
                else (AuthMethod.EXTERNAL if readiness.available else None)
            ),
            installed=not readiness.message.startswith(
                "claude_agent_sdk is not installed"
            )
            and not readiness.message.startswith("claude not found"),
            authenticated=(readiness.available if not direct else None),
            compatible=None,
            ready=readiness.available,
            live_tested=False,
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
            "Claude SDK authentication is external; set ANTHROPIC_API_KEY or "
            "authenticate with Claude Code before running Yoke."
        )

    async def run(self, harness: Harness, prompt: str, options: RunOptions) -> Run:
        """Execute a one-shot Claude run."""

        try:
            from claude_agent_sdk import query
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc

        sdk_options = claude_options(harness, options, env_overrides=self.env)
        messages = query(prompt=claude_prompt(prompt, sdk_options), options=sdk_options)
        return await collect_messages(
            self.provider,
            messages,
            surface=self.surface,
            output_schema=options.output_schema,
            requested_model=options.model or harness.agent.model,
        )

    async def models(self, harness: Harness):
        raise UnsupportedFeature("Claude model listing is not implemented in Yoke yet.")

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
                "Claude Python SDK is the runnable Claude surface in Yoke; "
                "Claude's documented native Workflow tool belongs to the "
                "TypeScript SDK surface."
            ),
        )

    async def goal_loop(
        self,
        harness: Harness,
        options: GoalLoopOptions,
    ) -> GoalRun:
        try:
            from claude_agent_sdk import query
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc

        messages = query(
            prompt=f"/goal {options.goal.objective}",
            options=claude_options(
                harness,
                RunOptions(goal=None, inherit_goal=False),
                env_overrides=self.env,
            ),
        )
        run = await collect_messages(self.provider, messages, surface=self.surface)
        session = run.session or Session(
            provider=self.provider,
            surface=self.surface,
            id=str(uuid4()),
            agent=harness.agent,
            cwd=harness.cwd,
        )
        return GoalRun(
            provider=self.provider,
            surface=self.surface,
            goal=options.goal,
            session=session.model_copy(update={"goal": options.goal}),
            auto_continues=True,
            status=run.status,
            failure=run.failure,
            raw=run,
        )

    async def list_sessions(
        self,
        harness: Harness,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        cwd: str | os.PathLike[str] | None = None,
        include_worktrees: bool = True,
    ) -> SessionList:
        if cursor is not None:
            raise UnsupportedFeature("Claude SDK session listing is not cursor-paged.")
        try:
            from claude_agent_sdk import list_sessions
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc
        directory = str(cwd or harness.cwd) if (cwd or harness.cwd) else None
        sessions = await asyncio.to_thread(
            list_sessions,
            directory=directory,
            limit=limit,
            include_worktrees=include_worktrees,
        )
        return SessionList(
            provider=self.provider,
            surface=self.surface,
            sessions=tuple(claude_session_summary(session) for session in sessions),
            raw=sessions,
        )

    async def read_session(
        self,
        harness: Harness,
        session_id: str,
        *,
        include_messages: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> SessionHistory:
        try:
            from claude_agent_sdk import get_session_info, get_session_messages
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc
        directory = str(harness.cwd) if harness.cwd else None
        info = await asyncio.to_thread(
            get_session_info,
            session_id,
            directory=directory,
        )
        raw_messages = ()
        if include_messages:
            raw_messages = await asyncio.to_thread(
                get_session_messages,
                session_id,
                directory=directory,
                limit=limit,
                offset=offset,
            )
        summary = (
            claude_session_summary(info)
            if info is not None
            else SessionSummary(
                provider=self.provider,
                surface=self.surface,
                id=session_id,
                provider_session_id=session_id,
            )
        )
        return SessionHistory(
            provider=self.provider,
            surface=self.surface,
            session=summary,
            messages=tuple(
                claude_session_message(session_id, message)
                for message in raw_messages
            ),
            raw={"info": info, "messages": raw_messages},
        )

    async def rename(self, session: Session, title: str) -> SessionSummary:
        try:
            from claude_agent_sdk import rename_session
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc
        session_id = session.provider_session_id or session.id
        directory = str(session.cwd) if session.cwd else None
        await asyncio.to_thread(
            rename_session,
            session_id,
            title,
            directory=directory,
        )
        return SessionSummary(
            provider=self.provider,
            surface=self.surface,
            id=session_id,
            provider_session_id=session_id,
            title=title,
            cwd=str(session.cwd) if session.cwd else None,
        )

    async def tag(self, session: Session, tag: str | None) -> SessionSummary:
        try:
            from claude_agent_sdk import tag_session
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc
        session_id = session.provider_session_id or session.id
        directory = str(session.cwd) if session.cwd else None
        await asyncio.to_thread(
            tag_session,
            session_id,
            tag,
            directory=directory,
        )
        return SessionSummary(
            provider=self.provider,
            surface=self.surface,
            id=session_id,
            provider_session_id=session_id,
            tag=tag,
            cwd=str(session.cwd) if session.cwd else None,
        )

    async def start(self, harness: Harness, options: SessionOptions) -> Session:
        """Start a Claude session.

        ClaudeSDKClient owns a live subprocess and must be closed by the caller.
        """

        try:
            from claude_agent_sdk import ClaudeSDKClient
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc

        run_options = RunOptions(
            model=options.model,
            goal=options.goal,
            inherit_goal=options.inherit_goal,
            effort=options.effort,
            permissions=options.permissions,
            provider=options.provider,
        )
        sdk_options = claude_options(
            harness,
            run_options,
            resume=options.resume,
            env_overrides=self.env,
        )
        client = ClaudeSDKClient(options=sdk_options)
        await client.connect()
        session_id = options.resume or str(uuid4())
        self._sessions[session_id] = ClaudeSession(
            client=client,
            options=sdk_options,
            provider_session_id=options.resume,
        )
        permissions = (
            options.permissions or harness.permissions or harness.agent.permissions
        )
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=session_id,
            provider_session_id=options.resume,
            agent=harness.agent,
            cwd=harness.cwd,
            permissions=permissions,
            goal=options.resolve_goal(harness.agent.goal),
            model=options.model or harness.agent.model,
            credentials=harness.credentials,
        )

    async def send(self, session: Session, turn: Turn, options: RunOptions) -> Run:
        live = self._sessions.get(session.id)
        if live is None:
            raise YokeError(f"Claude session is not live: {session.id}")
        await live.client.query(
            claude_prompt(turn.prompt, live.options),
            session_id=session.id,
        )
        run = await collect_messages(
            self.provider,
            live.client.receive_response(),
            session,
            requested_model=session.model,
        )
        live.provider_session_id = (
            run.session.provider_session_id if run.session else live.provider_session_id
        )
        return run

    async def stream(
        self,
        session: Session,
        turn: Turn,
        options: RunOptions,
    ) -> AsyncIterator[Event]:
        live = self._sessions.get(session.id)
        if live is None:
            raise YokeError(f"Claude session is not live: {session.id}")
        await live.client.query(
            claude_prompt(turn.prompt, live.options),
            session_id=session.id,
        )
        text: list[str] = []
        async for message in live.client.receive_response():
            events = claude_events(message)
            if type(message).__name__ == "ResultMessage":
                events = deduplicate_result_text(events, text)
            for event in events:
                if event.provider_session_id is not None:
                    live.provider_session_id = event.provider_session_id
                if event.kind == EventKind.TEXT and event.message is not None:
                    text.append(event.message)
                yield event.model_copy(update={"surface": self.surface})

    async def get_goal(self, session: Session) -> Goal | None:
        raise UnsupportedFeature("Claude does not expose native readable goals.")

    async def set_goal(self, session: Session, goal: Goal) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")

    async def clear_goal(self, session: Session) -> Session:
        raise UnsupportedFeature("Claude does not expose Codex-style mutable goals.")

    async def interrupt(self, session: Session) -> None:
        live = self._sessions.get(session.id)
        if live is None:
            raise YokeError(f"Claude session is not live: {session.id}")
        await live.client.interrupt()

    async def fork(self, session: Session, options: ForkOptions) -> Session:
        if session.agent is None or session.cwd is None:
            raise YokeError("Claude fork needs session agent and cwd.")
        if options.last_turn_id is not None:
            raise UnsupportedFeature(
                "Claude Python SDK live fork does not support last_turn_id."
            )
        if options.exclude_turns is not None:
            raise UnsupportedFeature(
                "Claude Python SDK live fork does not support exclude_turns."
            )
        try:
            from claude_agent_sdk import ClaudeSDKClient
        except ImportError as exc:
            raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc

        live = self._sessions.get(session.id)
        source_provider_id = session.provider_session_id or (
            live.provider_session_id if live else None
        )
        if source_provider_id is None:
            raise YokeError(
                "Claude fork needs provider_session_id from a persisted Claude "
                "session. Run a turn first so Yoke can learn the provider id."
            )
        fork_id = str(uuid4())
        harness = Harness(
            provider=self.provider,
            surface=self.surface,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions,
            credentials=session.credentials,
        )
        run_options = RunOptions(
            goal=session.goal,
            inherit_goal=False,
            permissions=session.permissions,
        )
        sdk_options = claude_options(
            harness,
            run_options,
            resume=source_provider_id,
            fork_session=True,
            env_overrides=self.env,
        )
        client = ClaudeSDKClient(options=sdk_options)
        await client.connect()
        self._sessions[fork_id] = ClaudeSession(client=client, options=sdk_options)
        return Session(
            provider=self.provider,
            surface=self.surface,
            id=fork_id,
            provider_session_id=None,
            agent=session.agent,
            cwd=session.cwd,
            permissions=session.permissions,
            goal=session.goal,
        )

    async def close(self, session: Session) -> None:
        live = self._sessions.pop(session.id, None)
        if live is not None:
            await live.client.disconnect()


@dataclass(slots=True)
class ClaudeSession:
    """Live Claude client plus provider-persisted session identity."""

    client: Any
    options: Any
    provider_session_id: str | None = None


def claude_prompt(prompt: str, options: Any) -> str | AsyncIterator[dict[str, Any]]:
    """Return the SDK prompt shape required by the selected Claude options."""

    if not claude_options_require_streaming_prompt(options):
        return prompt

    async def prompts() -> AsyncIterator[dict[str, Any]]:
        yield {
            "type": "user",
            "message": {"role": "user", "content": prompt},
        }

    return prompts()


def claude_options_require_streaming_prompt(options: Any) -> bool:
    """Return whether Claude SDK options require AsyncIterable prompts."""

    if getattr(options, "can_use_tool", None) is not None:
        return True
    kwargs = getattr(options, "kwargs", None)
    return isinstance(kwargs, dict) and kwargs.get("can_use_tool") is not None


def claude_options(
    harness: Harness,
    options: RunOptions,
    *,
    resume: str | None = None,
    fork_session: bool = False,
    env_overrides: dict[str, str] | None = None,
):
    try:
        from claude_agent_sdk import AgentDefinition as ClaudeAgentDefinition
        from claude_agent_sdk import ClaudeAgentOptions
    except ImportError as exc:
        raise YokeError(f"Claude support requires `{CLAUDE_INSTALL}`.") from exc

    agent = harness.agent
    goal = options.resolve_goal(agent.goal)
    plugins = claude_plugins(agent)
    skills = skill_names(agent)
    skill_filter = skills or ("all" if plugins else None)
    kwargs: dict[str, Any] = {
        "system_prompt": system_prompt(agent, goal),
        "cwd": harness.cwd,
        "model": options.model or agent.model,
        "effort": options.effort or agent.effort,
        "max_turns": options.max_turns,
        "permission_mode": permission_mode(
            harness,
            options.permissions,
            options.provider,
        ),
        "tools": tools(
            agent,
            options.provider,
            skills_enabled=skill_filter is not None,
        ),
        "allowed_tools": allowed_tools(
            agent,
            harness,
            options.permissions,
            options.provider,
            skills_enabled=skill_filter is not None,
        ),
        "disallowed_tools": disallowed_tools(
            agent,
            options.permissions or harness.permissions,
            options.provider,
        ),
        "agents": claude_agents(agent, options.provider, ClaudeAgentDefinition),
        "plugins": plugins or [],
        "skills": skill_filter,
        "output_format": output_format(provider_schema(options.output_schema)),
        "task_budget": {"total": goal.token_budget}
        if goal and goal.token_budget is not None
        else None,
        "resume": resume,
        "fork_session": fork_session,
        "env": credential_env(harness, env_overrides),
    }
    kwargs.update(claude_extra_options(options.provider, reserved=set(kwargs)))
    return ClaudeAgentOptions(**kwargs)


def credential_env(
    harness: Harness,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the Claude subprocess environment without mutating the process."""

    env = dict(os.environ)
    if overrides is not None:
        env.update(overrides)
    secret = harness.credentials.reveal()
    if harness.credentials.method is AuthMethod.API_KEY and secret is not None:
        env[ANTHROPIC_API_KEY] = secret
    elif harness.credentials.method is AuthMethod.OAUTH_TOKEN and secret is not None:
        env[CLAUDE_CODE_OAUTH_TOKEN] = secret
    return env


def claude_agents(agent: Agent, provider: Any | None, definition: Any):
    """Return Claude AgentDefinition map for Yoke subagents."""

    overrides = claude_agent_overrides(provider)
    agents = {
        name: definition(**claude_agent_kwargs(name, subagent, overrides.get(name)))
        for name, subagent in agent.subagents.items()
    }
    return agents or None


def claude_agent_kwargs(
    name: str,
    subagent: Agent,
    override: ClaudeAgentOptions | dict[str, Any] | None,
) -> dict[str, Any]:
    skills = skill_names(subagent)
    kwargs: dict[str, Any] = {
        "description": subagent.description or name,
        "prompt": subagent.instructions or subagent.description or name,
        "tools": claude_tools(subagent, skills_enabled=bool(skills)),
        "model": subagent.model,
        "skills": skills,
        "effort": subagent.effort,
        "permissionMode": permission_mode_for_agent(subagent),
        "disallowedTools": disallowed_tools(subagent, subagent.permissions),
    }
    kwargs.update(
        claude_agent_override_kwargs(override, reserved={"description", "prompt"})
    )
    if kwargs.get("skills") and kwargs.get("tools") is not None:
        kwargs["tools"] = include_claude_tool(kwargs["tools"], "Skill")
    return kwargs


def claude_agent_overrides(provider: Any | None) -> dict[str, Any]:
    if provider is None:
        return {}
    value = provider.claude
    if isinstance(value, ClaudeOptions):
        return value.agents
    if isinstance(value, dict):
        agents = value.get("agents")
        return agents if isinstance(agents, dict) else {}
    return {}


def claude_agent_override_kwargs(
    override: ClaudeAgentOptions | dict[str, Any] | None,
    *,
    reserved: set[str],
) -> dict[str, Any]:
    if override is None:
        return {}
    if isinstance(override, ClaudeAgentOptions):
        values = override.wire()
    elif isinstance(override, dict):
        raw = override.get("raw")
        values = dict(raw) if isinstance(raw, dict) else {}
        values.update({key: value for key, value in override.items() if key != "raw"})
    else:
        return {}
    return {
        claude_agent_wire_key(key): value
        for key, value in values.items()
        if claude_agent_wire_key(key) not in reserved and value is not None
    }


def claude_agent_wire_key(key: str) -> str:
    return {
        "disallowed_tools": "disallowedTools",
        "mcp_servers": "mcpServers",
        "initial_prompt": "initialPrompt",
        "max_turns": "maxTurns",
        "permission_mode": "permissionMode",
    }.get(key, key)


def claude_extra_options(provider: Any | None, *, reserved: set[str]) -> dict[str, Any]:
    """Return extra ClaudeAgentOptions kwargs from provider options."""

    if provider is None:
        return {}
    value = provider.claude
    if isinstance(value, ClaudeOptions):
        raw = value.raw
        request_handler = (
            value.request_handler
            or value.policy
            or raw.get("request_handler")
            or raw.get("requestHandler")
            or raw.get("policy")
        )
        extras = {
            "setting_sources": value.setting_sources,
            "include_partial_messages": value.include_partial_messages,
            "include_hook_events": value.include_hook_events,
            "max_budget_usd": value.max_budget_usd,
            "can_use_tool": value.can_use_tool
            or claude_request_callback(request_handler),
            "hooks": claude_hooks(value.hooks),
        }
    elif isinstance(value, dict):
        raw = dict(value.get("raw") or {})
        request_handler = (
            value.get("request_handler")
            or value.get("requestHandler")
            or value.get("policy")
            or raw.get("request_handler")
            or raw.get("requestHandler")
            or raw.get("policy")
        )
        extras = {
            "setting_sources": value.get("setting_sources"),
            "include_partial_messages": value.get("include_partial_messages"),
            "include_hook_events": value.get("include_hook_events"),
            "max_budget_usd": value.get("max_budget_usd"),
            "can_use_tool": value.get("can_use_tool", value.get("canUseTool"))
            or claude_request_callback(request_handler),
            "hooks": claude_hooks(value.get("hooks")),
        }
    else:
        return {}

    result = {}
    for key, item in raw.items():
        wire_key = claude_extra_option_wire_key(key)
        if wire_key == "request_handler":
            continue
        if wire_key not in reserved and item is not None:
            result[wire_key] = item
    for key, item in extras.items():
        if key not in reserved and item is not None:
            result[key] = item
    return result


def claude_hooks(value: object) -> object | None:
    """Lower Yoke hooks to Claude SDK HookMatcher dictionaries."""

    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if not isinstance(value, tuple | list):
        return value
    if not all(isinstance(hook, Hook) for hook in value):
        return value

    from claude_agent_sdk.types import HookMatcher

    grouped: dict[str, list[Any]] = {}
    for hook in value:
        grouped.setdefault(str(hook.event), []).append(
            HookMatcher(
                matcher=hook.matcher,
                hooks=list(hook.callbacks),
                timeout=hook.timeout,
            )
        )
    return grouped


def claude_extra_option_wire_key(key: str) -> str:
    """Return the Python ClaudeAgentOptions spelling for known extra options."""

    return {"canUseTool": "can_use_tool", "requestHandler": "request_handler"}.get(
        key, key
    )


def claude_request_callback(handler: object | None) -> object | None:
    """Wrap a Yoke request handler as Claude's can_use_tool callback."""

    if handler is None or not callable(handler):
        return None

    async def can_use_tool(tool_name: str, input_data: dict[str, Any], context: Any):
        event = claude_request_event(tool_name, input_data, context)
        response = handler(event, event.request.default if event.request else None)
        if inspect.isawaitable(response):
            response = await response
        return claude_permission_result(response, input_data)

    return can_use_tool


def claude_request_event(
    tool_name: str,
    input_data: dict[str, Any],
    context: Any,
) -> Event:
    """Return a Yoke event for one Claude can_use_tool callback."""

    kind = (
        EventKind.USER_INPUT_REQUEST
        if tool_name == "AskUserQuestion"
        else EventKind.APPROVAL_REQUEST
    )
    request_kind = (
        RequestKind.USER_INPUT
        if tool_name == "AskUserQuestion"
        else RequestKind.APPROVAL
    )
    default = Response.deny("Claude request denied by Yoke.")
    tool = claude_request_tool(tool_name, input_data)
    request = Request(
        kind=request_kind,
        id=claude_request_id(input_data, context),
        method=tool_name,
        message=claude_request_message(tool_name),
        tool=tool,
        input=input_data,
        default=default,
        raw=input_data,
    )
    return Event(
        kind=kind,
        message=request.message,
        tool_id=request.id,
        tool_name=tool_name,
        tool_input=json.dumps(input_data, sort_keys=True),
        tool=tool,
        request=request,
        response=default,
        raw=input_data,
    )


def claude_permission_result(response: object, input_data: dict[str, Any]) -> object:
    """Convert a Yoke response to a Claude SDK permission result."""

    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

    if response is None:
        response = Response.deny("Claude request handler returned no response.")
    if not isinstance(response, Response):
        if isinstance(response, dict):
            response = response_from_mapping(response)
        else:
            return response
    if response.decision in {"allow", "approve", "accept", "acceptForSession"}:
        updated_input = response.updated_input
        if updated_input is None and response.answers is not None:
            updated_input = {**input_data, "answers": response.answers}
        if updated_input is None:
            updated_input = input_data
        return PermissionResultAllow(
            updated_input=updated_input,
            updated_permissions=response.updated_permissions,
        )
    return PermissionResultDeny(
        message=response.message or "Denied by Yoke.",
        interrupt=response.interrupt,
    )


def response_from_mapping(value: dict[str, Any]) -> Response:
    """Coerce a handler dictionary into a Yoke response."""

    decision = value.get("decision") or value.get("behavior") or value.get("action")
    updated_input = value.get("updated_input", value.get("updatedInput"))
    updated_permissions = value.get(
        "updated_permissions",
        value.get("updatedPermissions"),
    )
    answers = value.get("answers")
    if decision is None and (updated_input is not None or answers is not None):
        decision = "allow"
    return Response(
        decision=str(decision) if decision is not None else None,
        message=value.get("message"),
        answers=answers if isinstance(answers, dict) else None,
        updated_input=updated_input,
        updated_permissions=updated_permissions,
        interrupt=bool(value.get("interrupt", False)),
        raw=value,
    )


def claude_request_tool(tool_name: str, input_data: dict[str, Any]) -> Tool:
    """Return display metadata for a Claude request callback."""

    if tool_name == "Bash":
        return Tool(
            kind=ToolKind.SHELL,
            title="Command approval",
            command=str(input_data.get("command"))
            if input_data.get("command") is not None
            else None,
            status=ToolStatus.STARTED,
        )
    if tool_name in {"Write", "Edit", "NotebookEdit"}:
        return Tool(
            kind=ToolKind.EDIT,
            title=f"{tool_name} approval",
            path=str(input_data.get("file_path") or input_data.get("path") or "")
            or None,
            status=ToolStatus.STARTED,
        )
    if tool_name in {"Read", "Glob", "Grep"}:
        return Tool(
            kind=ToolKind.READ if tool_name == "Read" else ToolKind.SEARCH,
            title=f"{tool_name} approval",
            path=str(input_data.get("file_path") or input_data.get("path") or "")
            or None,
            status=ToolStatus.STARTED,
        )
    if tool_name == "AskUserQuestion":
        return Tool(
            kind=ToolKind.UNKNOWN,
            title="Clarifying question",
            status=ToolStatus.STARTED,
        )
    return Tool(kind=ToolKind.UNKNOWN, title=tool_name, status=ToolStatus.STARTED)


def claude_request_id(input_data: dict[str, Any], context: Any) -> str | None:
    """Return a request id if Claude exposes one."""

    value = input_data.get("id") or input_data.get("tool_use_id")
    if value is None:
        value = getattr(context, "tool_use_id", None)
    return str(value) if value is not None else None


def claude_request_message(tool_name: str) -> str:
    """Return display text for a Claude callback request."""

    if tool_name == "AskUserQuestion":
        return "Claude asked a clarifying question"
    return f"Claude requested {tool_name} approval"


async def collect_messages(
    provider: Provider,
    messages: AsyncIterator[Any],
    session: Session | None = None,
    surface: str | None = None,
    output_schema: OutputSchema | None = None,
    requested_model: str | None = None,
) -> Run:
    events: list[Event] = []
    text: list[str] = []
    fallback_result: str | None = None
    data: Any | None = None
    usage: Usage | None = None
    failure: Failure | None = None
    resolved_surface = surface or (str(session.surface) if session else None)
    async for message in messages:
        mapped = claude_events(message)
        if type(message).__name__ == "ResultMessage":
            mapped = deduplicate_result_text(mapped, text)
        if resolved_surface is not None:
            mapped = [
                event.model_copy(update={"surface": resolved_surface})
                for event in mapped
            ]
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
                if isinstance(output_schema, type) and issubclass(
                    output_schema, BaseModel
                ):
                    try:
                        data = output_schema.model_validate(structured_output)
                    except ValidationError as error:
                        failure = Failure(
                            message=(
                                "provider structured output did not match schema"
                            ),
                            code="invalid_structured_output",
                            raw=str(error),
                        )
                else:
                    data = structured_output
                fallback_result = str(structured_output)
            elif result_text:
                fallback_result = str(result_text)
            terminal_failure = claude_result_failure(message)
            if terminal_failure is not None:
                failure = terminal_failure
    resolved_session = session_with_provider_id(session, events)
    return Run(
        provider=provider,
        surface=surface or (session.surface if session else None),
        output=("\n".join(text).strip() or fallback_result),
        data=data,
        events=tuple(events),
        session=resolved_session,
        usage=usage,
        requested_model=requested_model,
        status=RunStatus.FAILED if failure is not None else RunStatus.SUCCEEDED,
        failure=failure,
    )


def deduplicate_result_text(events: list[Event], prior_text: list[str]) -> list[Event]:
    """Drop Claude's terminal result copy when it repeats assistant text."""

    return [
        event
        for event in events
        if not (
            event.kind == EventKind.TEXT
            and event.message is not None
            and is_terminal_text_copy(event.message, prior_text)
        )
    ]


def is_terminal_text_copy(message: str, prior_text: list[str]) -> bool:
    """Whether terminal text repeats the assistant's immediately prior output."""

    if not prior_text:
        return False
    return message in {
        prior_text[-1],
        "".join(prior_text),
        "\n".join(prior_text),
    }


def claude_result_failure(message: Any) -> Failure | None:
    """Return terminal failure evidence carried by a Claude result."""

    permission_denials = getattr(message, "permission_denials", None)
    if permission_denials:
        count = len(permission_denials) if hasattr(permission_denials, "__len__") else 1
        request = "tool request" if count == 1 else "tool requests"
        return Failure(
            message=f"Claude denied {count} {request}",
            code="permission_denied",
            raw=str(permission_denials),
        )
    errors = getattr(message, "errors", None)
    api_error_status = getattr(message, "api_error_status", None)
    is_error = bool(getattr(message, "is_error", False))
    if not (is_error or errors or api_error_status):
        return None
    subtype = getattr(message, "subtype", None)
    code = str(subtype) if is_error and subtype else "provider_error"
    return Failure(
        message=result_error_message(errors, api_error_status),
        code=code,
    )


def session_with_provider_id(
    session: Session | None,
    events: list[Event],
) -> Session | None:
    """Return session with provider-native id learned from events."""

    if session is None:
        return None
    provider_session_id = session.provider_session_id
    for event in events:
        if event.provider_session_id is not None:
            provider_session_id = event.provider_session_id
    if provider_session_id == session.provider_session_id:
        return session
    return session.model_copy(update={"provider_session_id": provider_session_id})


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
                provider_parent_tool_use_id=getattr(
                    message,
                    "parent_tool_use_id",
                    None,
                ),
                raw=message,
            )
        ]
    if name == "HookEventMessage":
        return [hook_event(message)]
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
    if name == "TaskStartedMessage":
        return [task_started_event(message)]
    if name == "TaskProgressMessage":
        return [task_progress_event(message)]
    if name == "TaskNotificationMessage":
        return [task_notification_event(message)]
    if name == "TaskUpdatedMessage":
        return [task_updated_event(message)]
    return [Event(kind=name, raw=message)]


def assistant_events(message: Any) -> list[Event]:
    events: list[Event] = []
    for block in getattr(message, "content", []):
        block_name = type(block).__name__
        if block_name == "TextBlock":
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
        elif block_name == "ToolUseBlock":
            events.append(tool_use_event(message, block))
        elif block_name == "ToolResultBlock":
            events.append(tool_result_event(message, block))
        elif block_name == "ThinkingBlock":
            events.append(thinking_event(message, block))
        elif block_name == "ServerToolUseBlock":
            events.append(tool_use_event(message, block))
        elif block_name == "ServerToolResultBlock":
            events.append(tool_result_event(message, block))
    usage = claude_usage(getattr(message, "usage", None))
    if usage is not None:
        events.append(
            Event(
                kind="context_usage",
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
    return events or [Event(kind="stream_event", raw=message)]


def tool_use_event(message: Any, block: Any) -> Event:
    name = getattr(block, "name", None)
    tool_input = getattr(block, "input", None)
    return Event(
        kind="tool_use",
        message=tool_title(name, tool_input),
        tool_id=getattr(block, "id", None),
        tool_name=name,
        tool_input=(
            json.dumps(tool_input, sort_keys=True)
            if tool_input is not None
            else None
        ),
        tool=claude_tool(name, tool_input, ToolStatus.STARTED),
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=first_text(
            getattr(message, "uuid", None),
            getattr(message, "message_id", None),
        ),
        provider_parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
        raw=message,
    )


def thinking_event(message: Any, block: Any) -> Event:
    return Event(
        kind="tool_summary",
        message="thinking",
        tool_name="thinking",
        tool=Tool(
            kind=ToolKind.UNKNOWN,
            title="Thinking",
            status=ToolStatus.COMPLETED,
        ),
        tool_result={
            "signature": getattr(block, "signature", None),
            "has_thinking": bool(getattr(block, "thinking", None)),
        },
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=first_text(
            getattr(message, "uuid", None),
            getattr(message, "message_id", None),
        ),
        provider_parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
        raw=message,
    )


def tool_result_event(message: Any, block: Any) -> Event:
    content = getattr(block, "content", None)
    is_error = getattr(block, "is_error", None)
    status = ToolStatus.FAILED if is_error else ToolStatus.COMPLETED
    return Event(
        kind="tool_result",
        message=tool_result_message(content, is_error),
        tool_id=getattr(block, "tool_use_id", None),
        tool=Tool(status=status),
        tool_result=content,
        tool_is_error=is_error,
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=first_text(
            getattr(message, "uuid", None),
            getattr(message, "message_id", None),
        ),
        provider_parent_tool_use_id=getattr(message, "parent_tool_use_id", None),
        raw=message,
    )


def claude_tool(
    name: str | None,
    tool_input: Any,
    status: ToolStatus,
) -> Tool:
    values = tool_input if isinstance(tool_input, dict) else {}
    kind = claude_tool_kind(name)
    return Tool(
        kind=kind,
        title=name,
        path=first_text(
            values.get("file_path"),
            values.get("path"),
            values.get("notebook_path"),
        ),
        command=(
            values.get("command")
            if isinstance(values.get("command"), str)
            else None
        ),
        cwd=values.get("cwd") if isinstance(values.get("cwd"), str) else None,
        status=status,
    )


def claude_tool_kind(name: str | None) -> ToolKind:
    if name is None:
        return ToolKind.UNKNOWN
    if name.startswith("mcp__"):
        return ToolKind.MCP
    lowered = name.lower()
    if "web" in lowered:
        return ToolKind.WEB
    if "search" in lowered:
        return ToolKind.SEARCH
    if "code" in lowered or "bash" in lowered or "shell" in lowered:
        return ToolKind.SHELL
    return {
        "Read": ToolKind.READ,
        "Write": ToolKind.WRITE,
        "Edit": ToolKind.EDIT,
        "MultiEdit": ToolKind.EDIT,
        "NotebookEdit": ToolKind.EDIT,
        "Bash": ToolKind.SHELL,
        "BashOutput": ToolKind.SHELL,
        "KillBash": ToolKind.SHELL,
        "Grep": ToolKind.SEARCH,
        "Glob": ToolKind.SEARCH,
        "WebFetch": ToolKind.WEB,
        "WebSearch": ToolKind.WEB,
        "Agent": ToolKind.AGENT,
        "Task": ToolKind.AGENT,
    }.get(name, ToolKind.UNKNOWN)


def tool_title(name: str | None, tool_input: Any) -> str:
    if not name:
        return "tool use"
    values = tool_input if isinstance(tool_input, dict) else {}
    target = first_text(
        values.get("file_path"),
        values.get("path"),
        values.get("command"),
        values.get("query"),
        values.get("prompt"),
    )
    return f"{name}: {target}" if target else name


def tool_result_message(content: Any, is_error: bool | None) -> str:
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        return "tool failed" if is_error else "tool completed"
    if content is not None:
        return str(content)
    return "tool failed" if is_error else "tool completed"


def task_started_event(message: Any) -> Event:
    task_type = getattr(message, "task_type", None)
    description = getattr(message, "description", None)
    return Event(
        kind="tool_use",
        message=description or "background task started",
        tool_id=getattr(message, "task_id", None),
        tool_name=task_type,
        tool=Tool(
            kind=task_tool_kind(task_type),
            title=description,
            status=ToolStatus.STARTED,
        ),
        agent=task_agent_call(task_type, "started", description),
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=getattr(message, "uuid", None),
        provider_parent_tool_use_id=getattr(message, "tool_use_id", None),
        raw=message,
    )


def hook_event(message: Any) -> Event:
    hook_input = hook_input_dict(message)
    event_name = first_text(
        getattr(message, "hook_event_name", None),
        hook_input.get("hook_event_name"),
    )
    tool_input = hook_input.get("tool_input")
    agent = hook_agent_call(event_name, hook_input)
    return Event(
        kind="hook",
        message=hook_message(event_name, hook_input),
        tool_id=first_text(
            getattr(message, "tool_use_id", None),
            hook_input.get("tool_use_id"),
        ),
        tool_name=hook_input.get("tool_name")
        if isinstance(hook_input.get("tool_name"), str)
        else None,
        tool_input=(
            json.dumps(tool_input, sort_keys=True)
            if tool_input is not None
            else None
        ),
        tool=hook_tool(event_name, hook_input),
        tool_result=hook_tool_result(event_name, hook_input),
        tool_is_error=event_name == "PostToolUseFailure",
        agent=agent,
        provider_session_id=first_text(
            getattr(message, "session_id", None),
            hook_input.get("session_id"),
        ),
        provider_event_id=getattr(message, "uuid", None),
        provider_parent_tool_use_id=first_text(
            getattr(message, "parent_tool_use_id", None),
            hook_input.get("parent_tool_use_id"),
        ),
        raw=message,
    )


def hook_input_dict(message: Any) -> dict[str, Any]:
    for name in ("input", "hook_input", "hook_input_data"):
        value = getattr(message, name, None)
        if isinstance(value, dict):
            return value
    value = getattr(message, "data", None)
    return value if isinstance(value, dict) else {}


def hook_agent_call(
    event_name: str | None,
    hook_input: dict[str, Any],
) -> AgentCall | None:
    if event_name not in {
        "SubagentStart",
        "SubagentStop",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
    }:
        return None
    agent_id = hook_input.get("agent_id")
    agent_type = hook_input.get("agent_type")
    if event_name in {"PreToolUse", "PostToolUse", "PostToolUseFailure"} and not (
        isinstance(agent_id, str) or isinstance(agent_type, str)
    ):
        return None
    return AgentCall(
        action=hook_agent_action(event_name),
        agent_id=agent_id if isinstance(agent_id, str) else None,
        agent_type=agent_type if isinstance(agent_type, str) else None,
        states={
            "agent_transcript_path": hook_input.get("agent_transcript_path"),
            "stop_hook_active": hook_input.get("stop_hook_active"),
        }
        if event_name == "SubagentStop"
        else None,
    )


def hook_agent_action(event_name: str | None) -> str | None:
    return {
        "SubagentStart": "started",
        "SubagentStop": "stopped",
        "PreToolUse": "tool_starting",
        "PostToolUse": "tool_completed",
        "PostToolUseFailure": "tool_failed",
    }.get(str(event_name))


def hook_tool(event_name: str | None, hook_input: dict[str, Any]) -> Tool | None:
    if event_name == "SubagentStart":
        return Tool(
            kind=ToolKind.AGENT,
            title=first_text(hook_input.get("agent_type"), "subagent"),
            status=ToolStatus.STARTED,
        )
    if event_name == "SubagentStop":
        return Tool(
            kind=ToolKind.AGENT,
            title=first_text(hook_input.get("agent_type"), "subagent"),
            path=hook_input.get("agent_transcript_path")
            if isinstance(hook_input.get("agent_transcript_path"), str)
            else None,
            status=ToolStatus.COMPLETED,
        )
    if event_name in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
        tool = claude_tool(
            hook_input.get("tool_name")
            if isinstance(hook_input.get("tool_name"), str)
            else None,
            hook_input.get("tool_input"),
            hook_tool_status(event_name),
        )
        if event_name == "PostToolUseFailure":
            return tool.model_copy(
                update={
                    "summary": hook_input.get("error")
                    if isinstance(hook_input.get("error"), str)
                    else None
                }
            )
        return tool
    return None


def hook_tool_status(event_name: str | None) -> ToolStatus:
    return {
        "PreToolUse": ToolStatus.STARTED,
        "PostToolUse": ToolStatus.COMPLETED,
        "PostToolUseFailure": ToolStatus.FAILED,
    }.get(str(event_name), ToolStatus.COMPLETED)


def hook_tool_result(event_name: str | None, hook_input: dict[str, Any]) -> Any | None:
    if event_name == "PostToolUse":
        return hook_input.get("tool_response")
    if event_name == "PostToolUseFailure":
        return hook_input.get("error")
    return None


def hook_message(event_name: str | None, hook_input: dict[str, Any]) -> str | None:
    if event_name in {"SubagentStart", "SubagentStop"}:
        agent_type = hook_input.get("agent_type")
        if isinstance(agent_type, str) and agent_type:
            return f"{event_name}: {agent_type}"
    if event_name in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
        tool_name = hook_input.get("tool_name")
        agent_type = hook_input.get("agent_type")
        if isinstance(tool_name, str) and isinstance(agent_type, str):
            return f"{event_name}: {agent_type}.{tool_name}"
        if isinstance(tool_name, str):
            return f"{event_name}: {tool_name}"
    return event_name


def task_progress_event(message: Any) -> Event:
    usage, duration_ms = task_usage(getattr(message, "usage", None))
    last_tool_name = getattr(message, "last_tool_name", None)
    description = getattr(message, "description", None)
    return Event(
        kind="tool_summary",
        message=description or "background task progress",
        tool_id=getattr(message, "task_id", None),
        tool_name=last_tool_name,
        tool=Tool(
            kind=claude_tool_kind(last_tool_name),
            title=last_tool_name,
            status=ToolStatus.STARTED,
            duration_ms=duration_ms,
            summary=description,
        ),
        usage=usage,
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=getattr(message, "uuid", None),
        provider_parent_tool_use_id=getattr(message, "tool_use_id", None),
        raw=message,
    )


def task_notification_event(message: Any) -> Event:
    usage, duration_ms = task_usage(getattr(message, "usage", None))
    status = task_tool_status(getattr(message, "status", None))
    summary = getattr(message, "summary", None)
    output_file = getattr(message, "output_file", None)
    result = {
        "status": getattr(message, "status", None),
        "output_file": output_file,
        "summary": summary,
    }
    return Event(
        kind="tool_result",
        message=summary or "background task finished",
        tool_id=getattr(message, "task_id", None),
        tool=Tool(
            kind=ToolKind.UNKNOWN,
            status=status,
            path=output_file,
            duration_ms=duration_ms,
            summary=summary,
        ),
        tool_result=result,
        tool_is_error=status == ToolStatus.FAILED,
        usage=usage,
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=getattr(message, "uuid", None),
        provider_parent_tool_use_id=getattr(message, "tool_use_id", None),
        raw=message,
    )


def task_updated_event(message: Any) -> Event:
    patch = getattr(message, "patch", {}) or {}
    status = getattr(message, "status", None)
    if status is None and isinstance(patch, dict):
        status = patch.get("status")
    status_text = str(status) if status is not None else None
    terminal = status_text in {"completed", "failed", "stopped", "killed"}
    return Event(
        kind="tool_result" if terminal else "tool_summary",
        message=task_update_message(status_text, terminal),
        tool_id=getattr(message, "task_id", None),
        tool=Tool(
            kind=ToolKind.UNKNOWN,
            status=task_tool_status(status_text),
            summary=status_text,
        ),
        tool_result={
            "status": status_text,
            "patch": patch,
        },
        tool_is_error=status_text == "failed",
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=getattr(message, "uuid", None),
        raw=message,
    )


def task_update_message(status: str | None, terminal: bool) -> str:
    if status:
        prefix = "background task finished" if terminal else "background task updated"
        return f"{prefix}: {status}"
    return "background task finished" if terminal else "background task updated"


def task_tool_kind(task_type: str | None) -> ToolKind:
    return {
        "local_bash": ToolKind.SHELL,
        "local_agent": ToolKind.AGENT,
        "remote_agent": ToolKind.AGENT,
    }.get(str(task_type), ToolKind.UNKNOWN)


def task_tool_status(status: str | None) -> ToolStatus:
    return {
        "completed": ToolStatus.COMPLETED,
        "failed": ToolStatus.FAILED,
        "stopped": ToolStatus.DECLINED,
        "killed": ToolStatus.DECLINED,
        "pending": ToolStatus.STARTED,
        "running": ToolStatus.STARTED,
        "paused": ToolStatus.STARTED,
    }.get(str(status), ToolStatus.COMPLETED)


def task_agent_call(
    task_type: str | None,
    action: str,
    description: str | None,
) -> AgentCall | None:
    if task_tool_kind(task_type) != ToolKind.AGENT:
        return None
    return AgentCall(action=action, prompt=description)


def task_usage(value: Any) -> tuple[Usage | None, int | None]:
    if not isinstance(value, dict):
        return None, None
    total_tokens = first_int_field(value, "total_tokens", "totalTokens")
    duration_ms = first_int_field(value, "duration_ms", "durationMs")
    return Usage(total_tokens=total_tokens), duration_ms


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
                kind="text",
                message=str(result_text),
                provider_session_id=getattr(message, "session_id", None),
                provider_event_id=getattr(message, "uuid", None),
                raw=message,
            )
        )
    events.extend(result_pressure_events(message))
    if usage is not None:
        events.append(
            Event(
                kind="context_usage",
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


def result_pressure_events(message: Any) -> list[Event]:
    events: list[Event] = []
    provider_session_id = getattr(message, "session_id", None)
    provider_event_id = getattr(message, "uuid", None)
    errors = getattr(message, "errors", None)
    api_error_status = getattr(message, "api_error_status", None)
    if errors or api_error_status:
        events.append(
            Event(
                kind="error",
                message=result_error_message(errors, api_error_status),
                tool_result={
                    "errors": errors,
                    "api_error_status": api_error_status,
                },
                tool_is_error=True,
                provider_session_id=provider_session_id,
                provider_event_id=provider_event_id,
                raw=message,
            )
        )
    permission_denials = getattr(message, "permission_denials", None)
    if permission_denials:
        events.append(
            Event(
                kind="warning",
                message="Claude reported permission denials",
                tool_result={"permission_denials": permission_denials},
                provider_session_id=provider_session_id,
                provider_event_id=provider_event_id,
                raw=message,
            )
        )
    deferred_tool_use = getattr(message, "deferred_tool_use", None)
    if deferred_tool_use is not None:
        events.append(deferred_tool_use_event(message, deferred_tool_use))
    return events


def result_error_message(errors: Any, api_error_status: Any) -> str:
    if errors:
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, str):
                return first
            message = getattr(first, "message", None)
            if message:
                return str(message)
            if isinstance(first, dict) and first.get("message"):
                return str(first["message"])
        if isinstance(errors, str):
            return errors
    if api_error_status:
        return f"Claude API error: {api_error_status}"
    return "Claude result reported an error"


def deferred_tool_use_event(message: Any, deferred_tool_use: Any) -> Event:
    name = getattr(deferred_tool_use, "name", None)
    tool_input = getattr(deferred_tool_use, "input", None)
    return Event(
        kind="tool_request",
        message=f"deferred tool use: {name}" if name else "deferred tool use",
        tool_id=getattr(deferred_tool_use, "id", None),
        tool_name=name,
        tool_input=json.dumps(tool_input, sort_keys=True)
        if tool_input is not None
        else None,
        tool=claude_tool(name, tool_input, ToolStatus.STARTED),
        tool_result={"deferred": True, "input": tool_input},
        provider_session_id=getattr(message, "session_id", None),
        provider_event_id=getattr(message, "uuid", None),
        raw=message,
    )


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


def tools(
    agent: Agent,
    provider: Any | None = None,
    *,
    skills_enabled: bool = False,
) -> list[str] | dict[str, Any] | None:
    native = claude_provider_tools(provider)
    if native is not None:
        if skills_enabled:
            native = include_claude_tool(native, "Skill")
        return native
    names = claude_tools(agent, skills_enabled=skills_enabled)
    return names if names else None


def claude_tools(agent: Agent, *, skills_enabled: bool = False) -> list[str]:
    names: list[str] = []
    if agent.tools.read:
        names.extend(["Read", "Grep", "Glob"])
    if agent.tools.write:
        names.extend(["Write", "Edit"])
    if agent.tools.shell:
        names.append("Bash")
    if agent.tools.web:
        names.extend(["WebFetch", "WebSearch"])
    if agent.tools.agent or agent.subagents:
        names.append("Agent")
    if skills_enabled:
        names.append("Skill")
    return names


def include_claude_tool(tools_value: Any, tool: str) -> Any:
    """Return explicit Claude tools with `tool` included once."""

    if isinstance(tools_value, ClaudeToolset):
        return tools_value.model_dump()
    if isinstance(tools_value, dict):
        if tools_value.get("type") == "preset":
            return tools_value
        existing = tools_value.get("tools")
        if isinstance(existing, list) and tool not in existing:
            return {**tools_value, "tools": [*existing, tool]}
        return tools_value
    if isinstance(tools_value, tuple):
        return tools_value if tool in tools_value else (*tools_value, tool)
    if isinstance(tools_value, list):
        return tools_value if tool in tools_value else [*tools_value, tool]
    return tools_value


def allowed_tools(
    agent: Agent,
    harness: Harness,
    override: Any | None = None,
    provider: Any | None = None,
    *,
    skills_enabled: bool = False,
) -> list[str]:
    permissions = override or harness.permissions or agent.permissions
    names: list[str] = []
    if permissions.approval in (Approval.AUTO, Approval.NEVER):
        names.extend(
            accessible_claude_tools(
                agent,
                permissions,
                skills_enabled=skills_enabled,
            )
        )
    names.extend(claude_provider_tool_rules(provider, "allowed_tools"))
    return unique_strings(names)


def disallowed_tools(
    agent: Agent,
    permissions: Any | None = None,
    provider: Any | None = None,
) -> list[str]:
    permitted = set(accessible_claude_tools(agent, permissions or agent.permissions))
    names = [
        name
        for name in (
            "Read",
            "Grep",
            "Glob",
            "Write",
            "Edit",
            "Bash",
            "WebFetch",
            "WebSearch",
        )
        if name not in permitted
    ]
    if not agent.tools.agent and not agent.subagents:
        names.append("Agent")
    names.extend(claude_provider_tool_rules(provider, "disallowed_tools"))
    return unique_strings(names)


def accessible_claude_tools(
    agent: Agent,
    permissions: Any,
    *,
    skills_enabled: bool = False,
) -> list[str]:
    """Lower declared tools through Yoke's filesystem/network access bounds."""

    names: list[str] = []
    if agent.tools.read:
        names.extend(["Read", "Grep", "Glob"])
    if agent.tools.write and permissions.access in (Access.WRITE, Access.FULL):
        names.extend(["Write", "Edit"])
    if agent.tools.shell and permissions.access is Access.FULL:
        names.append("Bash")
    if agent.tools.web and permissions.network:
        names.extend(["WebFetch", "WebSearch"])
    if agent.tools.agent or agent.subagents:
        names.append("Agent")
    if skills_enabled:
        names.append("Skill")
    return names


def permission_mode(
    harness: Harness,
    override: Any | None = None,
    provider: Any | None = None,
) -> str | None:
    native = claude_provider_permission_mode(provider)
    if native is not None:
        return native
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


def claude_provider_permission_mode(provider: Any | None) -> str | None:
    value = claude_provider_option(provider, "permission_mode")
    if value is None:
        return None
    if isinstance(value, ClaudePermissionMode):
        return str(value)
    return str(value)


def claude_provider_tools(provider: Any | None) -> list[str] | dict[str, Any] | None:
    value = claude_provider_tools_value(provider)
    if value is None:
        return None
    if isinstance(value, ClaudeToolset):
        return value.model_dump()
    if isinstance(value, str):
        return [value]
    if isinstance(value, tuple | list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, dict):
        return value
    return None


def claude_provider_tools_value(provider: Any | None) -> Any | None:
    if provider is None:
        return None
    value = provider.claude
    if isinstance(value, ClaudeOptions):
        if value.tools is not None:
            return value.tools
        return value.raw.get("tools")
    if isinstance(value, dict):
        raw = value.get("raw")
        if value.get("tools") is not None:
            return value.get("tools")
        if isinstance(raw, dict):
            return raw.get("tools")
    return None


def claude_provider_tool_rules(provider: Any | None, field: str) -> list[str]:
    value = claude_provider_option(provider, field)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, tuple | list):
        return [str(item) for item in value if item is not None]
    return []


def claude_provider_option(provider: Any | None, field: str) -> Any | None:
    if provider is None:
        return None
    value = provider.claude
    if isinstance(value, ClaudeOptions):
        return getattr(value, field)
    if isinstance(value, dict):
        camel = {
            "permission_mode": "permissionMode",
            "allowed_tools": "allowedTools",
            "disallowed_tools": "disallowedTools",
        }[field]
        return value.get(field, value.get(camel))
    return None


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def claude_auth_status_message(stdout: str) -> str | None:
    """Return a readable message for `claude auth status` JSON output."""

    try:
        status = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(status, dict):
        return None
    if status.get("loggedIn") is False:
        return "Claude not logged in"
    if status.get("loggedIn") is not True:
        return None
    method = status.get("authMethod")
    provider = status.get("apiProvider")
    if isinstance(method, str) and method:
        return f"Claude authenticated via {method}"
    if isinstance(provider, str) and provider:
        return f"Claude authenticated via {provider}"
    return "Claude authenticated"


def claude_session_summary(session: Any) -> SessionSummary:
    session_id = str(getattr(session, "session_id", ""))
    return SessionSummary(
        provider="claude",
        surface="claude_python_sdk",
        id=session_id,
        provider_session_id=session_id,
        title=getattr(session, "custom_title", None),
        tag=getattr(session, "tag", None),
        summary=getattr(session, "summary", None)
        or getattr(session, "first_prompt", None),
        cwd=getattr(session, "cwd", None),
        created_at=getattr(session, "created_at", None),
        updated_at=getattr(session, "last_modified", None),
        raw=session,
    )


def claude_session_message(session_id: str, message: Any) -> SessionMessage:
    return SessionMessage(
        provider="claude",
        surface="claude_python_sdk",
        session_id=str(getattr(message, "session_id", None) or session_id),
        id=getattr(message, "uuid", None),
        role=getattr(message, "type", None),
        content=getattr(message, "message", None),
        raw=message,
    )


def skill_names(agent: Agent) -> list[str]:
    names: list[str] = []
    for skill in agent.skills:
        name = skill.name or (skill.path.stem if skill.path else None)
        if name is None:
            continue
        root = plugin_root_for_skill(skill.path)
        if root is not None:
            names.append(f"{root.expanduser().resolve().name}:{name}")
        else:
            names.append(name)
    return names


def claude_plugins(agent: Agent) -> list[dict[str, str]]:
    return [
        {"type": "local", "path": str(path)}
        for path in plugin_paths(agent)
    ]
