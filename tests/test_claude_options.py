from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from yoke import (
    Agent,
    ClaudeAgentOptions,
    ClaudeOptions,
    ClaudePermissionMode,
    ClaudeToolset,
    ClaudeToolsPreset,
    EventKind,
    ForkOptions,
    Goal,
    GoalLoopOptions,
    Harness,
    Hook,
    HookEvent,
    Permissions,
    ProviderOptions,
    RequestKind,
    RequestPolicy,
    Response,
    RunOptions,
    Session,
    Skill,
    ToolKind,
    register,
)
from yoke.errors import UnsupportedFeature, YokeError
from yoke.providers.claude import Claude, claude_options, claude_prompt


class StructuredDetail(BaseModel):
    label: str


class StructuredResult(BaseModel):
    detail: StructuredDetail


def test_claude_provider_options_reach_sdk_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test", model="sonnet"),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    setting_sources=("user", "project"),
                    include_partial_messages=True,
                    include_hook_events=True,
                    max_budget_usd=1.5,
                    raw={
                        "append_system_prompt": "extra",
                        "model": "should-not-override",
                    },
                )
            )
        ),
    )

    assert options.kwargs["setting_sources"] == ("user", "project")
    assert options.kwargs["include_partial_messages"] is True
    assert options.kwargs["include_hook_events"] is True
    assert options.kwargs["max_budget_usd"] == 1.5
    assert options.kwargs["append_system_prompt"] == "extra"
    assert options.kwargs["model"] == "sonnet"


def test_claude_prompt_uses_async_iterable_when_permissions_callback_present() -> None:
    async def can_use_tool(*_args, **_kwargs):
        return {"behavior": "allow"}

    async def collect(prompt):
        return [item async for item in prompt]

    options = SimpleNamespace(can_use_tool=can_use_tool)

    prompt = claude_prompt("hello", options)

    assert not isinstance(prompt, str)
    assert asyncio.run(collect(prompt)) == [
        {
            "type": "user",
            "message": {"role": "user", "content": "hello"},
        }
    ]


def test_claude_run_options_model_overrides_agent_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions(model="run-model"))

    assert options.kwargs["model"] == "run-model"


def test_claude_receives_provider_compatible_recursive_strict_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(output_schema=StructuredResult),
    )

    schema = options.kwargs["output_format"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["StructuredDetail"]["additionalProperties"] is False


def test_claude_path_skills_are_passed_as_explicit_plugin_skill_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    skill = tmp_path / "skills" / "release-check"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: release-check\n"
        "description: Check release notes.\n"
        "---\n"
        "Check release notes.\n"
    )
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test", skills=(Skill.from_path(skill),)),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions())

    assert options.kwargs["plugins"] == [
        {"type": "local", "path": str(tmp_path.resolve())}
    ]
    assert options.kwargs["skills"] == [f"{tmp_path.name}:release-check"]
    assert "Skill" in options.kwargs["tools"]


def test_claude_goal_loop_uses_slash_goal_through_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = fake_claude_agent_sdk()
    seen = {}

    class ResultMessage:
        subtype = "success"
        result = "goal accepted"

    async def fake_query(prompt, options):
        seen["prompt"] = prompt
        seen["options"] = options
        yield ResultMessage()

    module.query = fake_query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    goal = Goal("Finish the implementation safely.")
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path.cwd(),
    )

    result = asyncio.run(Claude().goal_loop(harness, GoalLoopOptions(goal=goal)))

    assert seen["prompt"] == "/goal Finish the implementation safely."
    assert seen["options"].kwargs["model"] == "agent-model"
    assert result.ok
    assert result.goal == goal
    assert result.session.goal == goal


def test_claude_provider_permission_options_reach_sdk_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    permission_mode=ClaudePermissionMode.DONT_ASK,
                    allowed_tools=("Read", "Glob"),
                    disallowed_tools=("Bash(rm *)",),
                )
            )
        ),
    )

    assert options.kwargs["permission_mode"] == "dontAsk"
    assert options.kwargs["allowed_tools"] == ["Read", "Glob"]
    assert options.kwargs["disallowed_tools"] == [
        "Write",
        "Edit",
        "Bash",
        "WebFetch",
        "WebSearch",
        "Agent",
        "Bash(rm *)",
    ]


def test_claude_provider_tools_override_base_available_toolset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    tools=("Read",),
                    allowed_tools=("Read",),
                )
            )
        ),
    )

    assert options.kwargs["tools"] == ["Read"]
    assert options.kwargs["allowed_tools"] == ["Read"]


def test_claude_provider_tools_preset_lowers_to_sdk_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    tools=ClaudeToolset(preset=ClaudeToolsPreset.CLAUDE_CODE)
                )
            )
        ),
    )

    assert options.kwargs["tools"] == {
        "type": "preset",
        "preset": "claude_code",
    }


def test_claude_runtime_permission_callbacks_reach_sdk_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    async def can_use_tool(*_args, **_kwargs):
        return None

    async def block_writes(*_args, **_kwargs):
        return {"decision": "block"}

    hooks = {"PreToolUse": (block_writes,)}
    claude = ClaudeOptions(can_use_tool=can_use_tool, hooks=hooks)
    run_options = RunOptions(provider=ProviderOptions(claude=claude))

    options = claude_options(harness, run_options)
    runtime = {item.path: item.reason for item in run_options.runtime_options()}

    assert options.kwargs["can_use_tool"] is can_use_tool
    assert options.kwargs["hooks"] is hooks
    assert "can_use_tool" not in claude.model_dump()
    assert "hooks" not in claude.model_dump()
    assert "provider.claude.can_use_tool" in runtime
    assert "provider.claude.hooks" in runtime


def test_claude_typed_hooks_lower_to_sdk_hook_matchers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    monkeypatch.setitem(sys.modules, "claude_agent_sdk.types", fake_claude_types())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    async def check_bash(*_args, **_kwargs):
        return {}

    hook = Hook(
        HookEvent.PRE_TOOL_USE,
        matcher="Bash",
        callbacks=(check_bash,),
        timeout=5,
    )
    run_options = RunOptions(
        provider=ProviderOptions(claude=ClaudeOptions(hooks=(hook,)))
    )

    options = claude_options(harness, run_options)
    hooks = options.kwargs["hooks"]
    matcher = hooks["PreToolUse"][0]
    runtime = {item.path: item.reason for item in run_options.runtime_options()}

    assert matcher.matcher == "Bash"
    assert matcher.hooks == [check_bash]
    assert matcher.timeout == 5
    assert "provider.claude.hooks" in runtime
    assert "callbacks" not in hook.model_dump()


def test_claude_request_handler_wraps_can_use_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    monkeypatch.setitem(sys.modules, "claude_agent_sdk.types", fake_claude_types())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    seen = []

    async def request_handler(event, default):
        seen.append((event, default))
        return Response.allow()

    claude = ClaudeOptions(request_handler=request_handler)
    run_options = RunOptions(provider=ProviderOptions(claude=claude))
    options = claude_options(harness, run_options)
    callback = options.kwargs["can_use_tool"]
    input_data = {"id": "req-1", "command": "pytest"}

    result = asyncio.run(
        callback("Bash", input_data, SimpleNamespace(tool_use_id="ctx-1"))
    )
    runtime = {item.path: item.reason for item in run_options.runtime_options()}

    assert len(seen) == 1
    event, default = seen[0]
    assert event.kind is EventKind.APPROVAL_REQUEST
    assert event.request is not None
    assert event.request.kind is RequestKind.APPROVAL
    assert event.request.id == "req-1"
    assert event.request.method == "Bash"
    assert event.request.input == input_data
    assert event.tool is not None
    assert event.tool.kind is ToolKind.SHELL
    assert event.tool.command == "pytest"
    assert default.decision == "deny"
    assert result.updated_input == input_data
    assert result.updated_permissions is None
    assert "request_handler" not in claude.model_dump()
    assert "provider.claude.request_handler" in runtime


def test_claude_request_handler_supports_ask_user_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    monkeypatch.setitem(sys.modules, "claude_agent_sdk.types", fake_claude_types())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    seen = []

    def request_handler(event, _default):
        seen.append(event)
        return {"answers": {"How should I format it?": "Summary"}}

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(request_handler=request_handler)
            )
        ),
    )
    input_data = {
        "questions": [
            {
                "question": "How should I format it?",
                "header": "Format",
                "options": [{"label": "Summary", "description": "Brief"}],
                "multiSelect": False,
            }
        ]
    }

    result = asyncio.run(
        options.kwargs["can_use_tool"](
            "AskUserQuestion",
            input_data,
            SimpleNamespace(),
        )
    )

    assert seen[0].kind is EventKind.USER_INPUT_REQUEST
    assert seen[0].request is not None
    assert seen[0].request.kind is RequestKind.USER_INPUT
    assert result.updated_input == {
        **input_data,
        "answers": {"How should I format it?": "Summary"},
    }


def test_claude_request_handler_accepts_neutral_request_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    monkeypatch.setitem(sys.modules, "claude_agent_sdk.types", fake_claude_types())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    request_handler=RequestPolicy.allow_tools(ToolKind.SHELL)
                )
            )
        ),
    )
    input_data = {"command": "pytest"}

    allowed = asyncio.run(
        options.kwargs["can_use_tool"]("Bash", input_data, SimpleNamespace())
    )
    denied = asyncio.run(
        options.kwargs["can_use_tool"]("Write", {"file_path": "x"}, SimpleNamespace())
    )

    assert allowed.updated_input == input_data
    assert denied.message == "Claude request denied by Yoke."


def test_claude_policy_is_serializable_request_callback_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    monkeypatch.setitem(sys.modules, "claude_agent_sdk.types", fake_claude_types())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    claude = ClaudeOptions(policy=RequestPolicy.allow_tools(ToolKind.SHELL))
    run_options = RunOptions(provider=ProviderOptions(claude=claude))

    options = claude_options(harness, run_options)

    assert callable(options.kwargs["can_use_tool"])
    assert run_options.runtime_options() == ()
    assert claude.model_dump()["policy"]["tool_kinds"] == ("shell",)


def test_claude_provider_options_accept_raw_dict_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    def can_use_tool(*_args, **_kwargs):
        return None

    def hook(*_args, **_kwargs):
        return {"decision": "allow"}

    hooks = {"PreToolUse": (hook,)}

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude={
                    "setting_sources": ("project",),
                    "permissionMode": "plan",
                    "allowedTools": ("Read",),
                    "canUseTool": can_use_tool,
                    "hooks": hooks,
                    "raw": {"include_partial_messages": True},
                }
            )
        ),
    )

    assert options.kwargs["setting_sources"] == ("project",)
    assert options.kwargs["permission_mode"] == "plan"
    assert options.kwargs["allowed_tools"] == ["Read"]
    assert options.kwargs["can_use_tool"] is can_use_tool
    assert options.kwargs["hooks"] is hooks
    assert options.kwargs["include_partial_messages"] is True


def test_claude_subagent_options_reach_agent_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="main",
            subagents={
                "reviewer": Agent(
                    instructions="review code",
                    description="Review code",
                    model="sonnet",
                )
            },
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude=ClaudeOptions(
                    agents={
                        "reviewer": ClaudeAgentOptions(
                            tools=("Read", "Grep"),
                            disallowed_tools=("Bash",),
                            model="opus",
                            skills=("security",),
                            memory="project",
                            mcp_servers=("github",),
                            initial_prompt="Start here.",
                            max_turns=3,
                            background=True,
                            effort="high",
                            permission_mode="acceptEdits",
                        )
                    }
                )
            )
        ),
    )

    reviewer = options.kwargs["agents"]["reviewer"]
    assert reviewer.kwargs["description"] == "Review code"
    assert reviewer.kwargs["prompt"] == "review code"
    assert reviewer.kwargs["tools"] == ("Read", "Grep", "Skill")
    assert reviewer.kwargs["disallowedTools"] == ("Bash",)
    assert reviewer.kwargs["model"] == "opus"
    assert reviewer.kwargs["skills"] == ("security",)
    assert reviewer.kwargs["memory"] == "project"
    assert reviewer.kwargs["mcpServers"] == ("github",)
    assert reviewer.kwargs["initialPrompt"] == "Start here."
    assert reviewer.kwargs["maxTurns"] == 3
    assert reviewer.kwargs["background"] is True
    assert reviewer.kwargs["effort"] == "high"
    assert reviewer.kwargs["permissionMode"] == "acceptEdits"


def test_claude_subagent_options_accept_raw_dict_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="main",
            subagents={"reviewer": Agent(instructions="review code")},
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(
            provider=ProviderOptions(
                claude={
                    "agents": {
                        "reviewer": {
                            "tools": ("Read",),
                            "raw": {"background": True},
                        }
                    }
                }
            )
        ),
    )

    reviewer = options.kwargs["agents"]["reviewer"]
    assert reviewer.kwargs["tools"] == ("Read",)
    assert reviewer.kwargs["background"] is True


def test_claude_subagent_path_skills_enable_skill_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    skill = tmp_path / "skills" / "audit"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: audit\n"
        "description: Audit source evidence.\n"
        "---\n"
        "Audit source evidence.\n"
    )
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="main",
            subagents={
                "reviewer": Agent(
                    instructions="review code",
                    skills=(Skill.from_path(skill),),
                )
            },
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions())

    reviewer = options.kwargs["agents"]["reviewer"]
    assert reviewer.kwargs["skills"] == [f"{tmp_path.name}:audit"]
    assert "Skill" in reviewer.kwargs["tools"]


def test_claude_declared_subagents_enable_agent_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="main",
            subagents={"reviewer": Agent(instructions="review code")},
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions())

    assert "Agent" in options.kwargs["tools"]
    assert "Agent" not in options.kwargs["disallowed_tools"]


def test_claude_declared_subagents_auto_approval_allows_agent_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="main",
            subagents={"reviewer": Agent(instructions="review code")},
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(
        harness,
        RunOptions(permissions=Permissions(approval="auto")),
    )

    assert "Agent" in options.kwargs["allowed_tools"]


def test_claude_never_approval_preapproves_only_accessible_declared_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="create a file",
            tools={"read": True, "write": True, "shell": True, "web": True},
            permissions=Permissions(access="write", approval="never", network=False),
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions())

    assert options.kwargs["permission_mode"] == "dontAsk"
    assert options.kwargs["allowed_tools"] == [
        "Read",
        "Grep",
        "Glob",
        "Write",
        "Edit",
    ]
    assert "Bash" in options.kwargs["disallowed_tools"]
    assert "WebFetch" in options.kwargs["disallowed_tools"]
    assert "WebSearch" in options.kwargs["disallowed_tools"]


def test_claude_read_access_denies_declared_mutating_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    harness = Harness(
        provider="claude",
        surface="claude_python_sdk",
        agent=Agent(
            instructions="inspect only",
            tools={"read": True, "write": True, "shell": True},
            permissions=Permissions(access="read", approval="never"),
        ),
        cwd=Path.cwd(),
    )

    options = claude_options(harness, RunOptions())

    assert options.kwargs["allowed_tools"] == ["Read", "Grep", "Glob"]
    assert all(
        tool in options.kwargs["disallowed_tools"]
        for tool in ("Write", "Edit", "Bash")
    )


@pytest.mark.asyncio
async def test_claude_fork_starts_resume_fork_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_claude_agent_sdk()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake)
    adapter = register(Claude())
    session = Session(
        provider="claude",
        surface="claude_python_sdk",
        id="local-session",
        provider_session_id="provider-session",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    forked = await session.fork()

    assert forked.id != session.id
    assert forked.provider_session_id is None
    assert fake.last_client.connected
    assert fake.last_client.options.kwargs["resume"] == "provider-session"
    assert fake.last_client.options.kwargs["fork_session"] is True
    await forked.close()
    assert fake.last_client.disconnected
    assert adapter is not None


@pytest.mark.asyncio
async def test_claude_fork_requires_provider_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    register(Claude())
    session = Session(
        provider="claude",
        surface="claude_python_sdk",
        id="local-session",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    with pytest.raises(YokeError, match="provider_session_id"):
        await session.fork()


@pytest.mark.asyncio
async def test_claude_fork_rejects_partial_fork(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_claude_agent_sdk())
    register(Claude())
    session = Session(
        provider="claude",
        surface="claude_python_sdk",
        id="local-session",
        provider_session_id="provider-session",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    with pytest.raises(UnsupportedFeature, match="last_turn_id"):
        await session.fork(ForkOptions(last_turn_id="message-id"))


def fake_claude_agent_sdk() -> SimpleNamespace:
    class FakeAgentDefinition:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeClaudeAgentOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeClaudeSDKClient:
        def __init__(self, options):
            self.options = options
            self.connected = False
            self.disconnected = False
            module.last_client = self

        async def connect(self):
            self.connected = True

        async def disconnect(self):
            self.disconnected = True

    module = SimpleNamespace()
    module.AgentDefinition = FakeAgentDefinition
    module.ClaudeAgentOptions = FakeClaudeAgentOptions
    module.ClaudeSDKClient = FakeClaudeSDKClient
    return module


def fake_claude_types() -> SimpleNamespace:
    class FakeHookMatcher:
        def __init__(self, matcher=None, hooks=None, timeout=None):
            self.matcher = matcher
            self.hooks = hooks or []
            self.timeout = timeout

    class FakePermissionResultAllow:
        def __init__(self, updated_input=None, updated_permissions=None):
            self.updated_input = updated_input
            self.updated_permissions = updated_permissions

    class FakePermissionResultDeny:
        def __init__(self, message: str, interrupt: bool = False):
            self.message = message
            self.interrupt = interrupt

    module = SimpleNamespace()
    module.HookMatcher = FakeHookMatcher
    module.PermissionResultAllow = FakePermissionResultAllow
    module.PermissionResultDeny = FakePermissionResultDeny
    return module
