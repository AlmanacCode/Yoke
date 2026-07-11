from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from yoke import (
    Agent,
    CodexApproval,
    CodexAppServerExposure,
    CodexAppServerOptions,
    CodexOptions,
    CodexReviewer,
    CodexSandbox,
    Collaboration,
    CollaborationSettings,
    ForkOptions,
    Harness,
    Permissions,
    ProviderOptions,
    RequestPolicy,
    RunOptions,
    Session,
    SessionOptions,
    ToolKind,
    Turn,
    runtime_options,
)
from yoke.errors import YokeError
from yoke.providers.codex_app.events import TurnResult
from yoke.providers.codex_app_server import (
    AppServerThread,
    CodexAppServer,
    codex_collaboration_mode,
    codex_experimental_api,
    codex_initialize_capabilities,
    codex_options,
    codex_request_handler,
    fork_params,
    initialize_params,
    parse_models,
    require_experimental_api,
    thread_params,
    turn_params,
)


def test_codex_collaboration_mode_accepts_snake_or_camel_case() -> None:
    snake = {"mode": "plan", "settings": {"developer_instructions": None}}
    camel = {"mode": "default", "settings": {"developer_instructions": "work"}}

    assert codex_collaboration_mode({"collaboration_mode": snake}) == snake
    assert codex_collaboration_mode({"collaborationMode": camel}) == camel
    assert codex_collaboration_mode({"collaboration_mode": "plan"}) is None


def test_codex_collaboration_mode_accepts_typed_options() -> None:
    collaboration = Collaboration(
        mode="plan",
        settings=CollaborationSettings(
            developer_instructions=None,
            model="gpt-5.4-mini",
            reasoning_effort="medium",
        ),
    )

    assert codex_collaboration_mode(CodexOptions(collaboration=collaboration)) == {
        "mode": "plan",
        "settings": {
            "developer_instructions": None,
            "model": "gpt-5.4-mini",
            "reasoning_effort": "medium",
        },
    }


def test_codex_options_accept_experimental_api_aliases() -> None:
    assert CodexOptions(experimental_api=True).experimental_api is True
    assert (
        CodexOptions.model_validate({"experimentalApi": True}).experimental_api
        is True
    )


def test_codex_options_accept_app_server_experimental_aliases() -> None:
    options = CodexOptions.model_validate(
        {
            "permissions": ":workspace",
            "runtimeWorkspaceRoots": ["/tmp/yoke", "/tmp/shared"],
            "environments": [{"environmentId": "local", "cwd": "/tmp/yoke"}],
            "selectedCapabilityRoots": [
                {
                    "id": "github@openai",
                    "location": {
                        "type": "environment",
                        "environmentId": "workspace",
                        "path": "/opt/plugins/github",
                    },
                }
            ],
            "allowProviderModelFallback": True,
            "serviceTier": "priority",
            "clientUserMessageId": "client-message-1",
        }
    )

    assert options.permissions == ":workspace"
    assert options.runtime_workspace_roots == ("/tmp/yoke", "/tmp/shared")
    assert options.environments == (
        {"environmentId": "local", "cwd": "/tmp/yoke"},
    )
    assert options.selected_capability_roots == (
        {
            "id": "github@openai",
            "location": {
                "type": "environment",
                "environmentId": "workspace",
                "path": "/opt/plugins/github",
            },
        },
    )
    assert options.allow_provider_model_fallback is True
    assert options.service_tier == "priority"
    assert options.client_user_message_id == "client-message-1"
    assert options.has_app_server_experimental_fields()
    assert codex_experimental_api(options) is True


def test_initialize_params_only_opts_into_experimental_api_when_requested() -> None:
    stable = initialize_params(
        name="yoke",
        title="Yoke",
        version="0.0.0",
    )
    experimental = initialize_params(
        name="yoke",
        title="Yoke",
        version="0.0.0",
        capabilities={"experimentalApi": True},
    )

    assert "capabilities" not in stable
    assert experimental["capabilities"] == {"experimentalApi": True}


def test_codex_app_server_options_build_initialize_capabilities() -> None:
    options = CodexOptions(
        experimental_api=True,
        app_server=CodexAppServerOptions(
            opt_out_notification_methods=(
                "thread/started",
                "item/agentMessage/delta",
            ),
            mcp_server_openai_form_elicitation=True,
        ),
    )

    assert codex_initialize_capabilities(options) == {
        "experimentalApi": True,
        "optOutNotificationMethods": [
            "thread/started",
            "item/agentMessage/delta",
        ],
        "mcpServerOpenaiFormElicitation": True,
    }


def test_codex_app_server_options_can_carry_request_handler() -> None:
    def handler(event, default):
        return None

    options = CodexOptions(
        app_server=CodexAppServerOptions(request_handler=handler)
    )

    assert codex_request_handler(options) is handler
    assert "request_handler" not in options.model_dump()["app_server"]


def test_codex_app_server_options_can_carry_serializable_policy() -> None:
    policy = RequestPolicy.allow_tools(ToolKind.SHELL)
    options = CodexOptions(app_server=CodexAppServerOptions(policy=policy))

    assert codex_request_handler(options) == policy
    assert options.runtime_options() == ()
    assert options.model_dump()["app_server"]["policy"]["tool_kinds"] == ("shell",)


def test_runtime_options_report_sdk_only_request_handler() -> None:
    def handler(event, default):
        return None

    options = RunOptions(
        provider=ProviderOptions(
            codex=CodexOptions(
                app_server=CodexAppServerOptions(request_handler=handler)
            )
        )
    )

    report = options.runtime_options()

    assert report == runtime_options(options)
    assert len(report) == 1
    assert report[0].path == "provider.codex.app_server.request_handler"
    assert "Callbacks are live Python objects" in report[0].reason
    assert "request_handler" not in options.model_dump()["provider"]["codex"][
        "app_server"
    ]


def test_runtime_options_ignores_unset_runtime_only_fields() -> None:
    assert CodexAppServerOptions().runtime_options() == ()


def test_runtime_options_reports_callable_values_in_raw_escape_hatches() -> None:
    def callback():
        return None

    options = RunOptions(
        provider=ProviderOptions(codex=CodexOptions(raw={"callback": callback}))
    )

    report = options.runtime_options()

    assert len(report) == 1
    assert report[0].path == "provider.codex.raw.callback"
    assert "Callables are live Python objects" in report[0].reason


def test_codex_app_server_exposure_splits_protocol_and_runtime_fields() -> None:
    def handler(event, default):
        return default

    options = CodexOptions(
        experimental_api=True,
        app_server=CodexAppServerOptions(
            request_handler=handler,
            opt_out_notification_methods=("thread/started",),
            mcp_server_openai_form_elicitation=True,
        ),
    )

    exposure = options.app_server_exposure()

    assert isinstance(exposure, CodexAppServerExposure)
    assert exposure.stable == (
        "initialize.capabilities.optOutNotificationMethods",
        "initialize.capabilities.mcpServerOpenaiFormElicitation",
    )
    assert exposure.experimental == ("initialize.capabilities.experimentalApi",)
    assert len(exposure.runtime) == 1
    assert exposure.runtime[0].path == "request_handler"


def test_codex_app_server_exposure_accepts_raw_app_server_dict() -> None:
    options = CodexOptions.model_validate(
        {
            "appServer": {
                "optOutNotificationMethods": ["thread/started"],
            },
        }
    )

    exposure = options.app_server_exposure()

    assert exposure.stable == ("initialize.capabilities.optOutNotificationMethods",)
    assert exposure.experimental == ()
    assert exposure.runtime == ()


def test_codex_app_server_options_accept_camel_case_and_raw_dicts() -> None:
    typed = CodexOptions.model_validate(
        {
            "experimentalApi": True,
            "appServer": {
                "optOutNotificationMethods": ["thread/started"],
                "mcpServerOpenaiFormElicitation": True,
            },
        }
    )
    raw = {
        "experimentalApi": True,
        "appServer": {
            "optOutNotificationMethods": ["thread/started"],
            "mcpServerOpenaiFormElicitation": True,
        },
    }

    assert codex_initialize_capabilities(typed) == codex_initialize_capabilities(raw)


def test_codex_options_preserve_legacy_dict_shape() -> None:
    collaboration_mode = {"mode": "plan", "settings": {"developer_instructions": None}}
    options = SessionOptions(
        provider=ProviderOptions(codex={"collaboration_mode": collaboration_mode})
    )

    assert codex_collaboration_mode(codex_options(options)) == collaboration_mode


def test_turn_params_include_typed_provider_collaboration_mode() -> None:
    collaboration_mode = {
        "mode": "plan",
        "settings": {
            "developer_instructions": None,
            "model": "gpt-5.4-mini",
            "reasoning_effort": "medium",
        },
    }
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort="high",
        provider_options=CodexOptions(collaboration=collaboration_mode),
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root", model="gpt-5.1"),
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
    )

    params = turn_params(
        thread,
        session,
        Turn(prompt="Use collaboration mode."),
        {"type": "object"},
    )

    assert params["threadId"] == "thread-1"
    assert params["input"][0]["text"] == "Use collaboration mode."
    assert params["model"] == "gpt-5.1"
    assert params["effort"] == "high"
    assert params["outputSchema"] == {"type": "object"}
    assert params["collaborationMode"] == collaboration_mode


def test_thread_params_can_use_session_model_override() -> None:
    params = thread_params(
        Harness(
            provider="codex",
            surface="codex_app_server",
            agent=Agent(instructions="root", model="agent-model"),
            cwd=Path("/tmp/yoke"),
        ),
        Permissions(),
        None,
        False,
        {},
        model="session-model",
    )

    assert params["model"] == "session-model"


def test_thread_params_include_app_server_native_thread_options() -> None:
    params = thread_params(
        Harness(
            provider="codex",
            surface="codex_app_server",
            agent=Agent(instructions="root", model="agent-model"),
            cwd=Path("/tmp/yoke"),
        ),
        Permissions(),
        None,
        False,
        CodexOptions(
            permissions=":workspace",
            approvals_reviewer=CodexReviewer.AUTO_REVIEW,
            runtime_workspace_roots=("/tmp/yoke", "/tmp/shared"),
            environments=({"environmentId": "local", "cwd": "/tmp/yoke"},),
            selected_capability_roots=(
                {
                    "id": "github@openai",
                    "location": {
                        "type": "environment",
                        "environmentId": "workspace",
                        "path": "/opt/plugins/github",
                    },
                },
            ),
            allow_provider_model_fallback=True,
            service_tier="priority",
        ),
    )

    assert params["permissions"] == ":workspace"
    assert "sandbox" not in params
    assert params["approvalsReviewer"] == "auto_review"
    assert params["runtimeWorkspaceRoots"] == ["/tmp/yoke", "/tmp/shared"]
    assert params["environments"] == [{"environmentId": "local", "cwd": "/tmp/yoke"}]
    assert params["selectedCapabilityRoots"] == [
        {
            "id": "github@openai",
            "location": {
                "type": "environment",
                "environmentId": "workspace",
                "path": "/opt/plugins/github",
            },
        }
    ]
    assert params["allowProviderModelFallback"] is True
    assert params["serviceTier"] == "priority"


def test_turn_params_can_use_run_or_turn_model_override() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root", model="agent-model"),
        cwd=Path("/tmp/yoke"),
    )

    turn_override = turn_params(
        thread,
        session,
        Turn(prompt="Use turn model.", model="turn-model"),
        None,
    )
    run_override = turn_params(
        thread,
        session,
        Turn(prompt="Use run model.", model="turn-model"),
        None,
        model="run-model",
    )

    assert turn_override["model"] == "turn-model"
    assert run_override["model"] == "run-model"


def test_turn_params_include_app_server_native_turn_options() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options=CodexOptions(
            permissions=":workspace",
            approvals_reviewer=CodexReviewer.AUTO_REVIEW,
            runtime_workspace_roots=("/tmp/yoke", "/tmp/shared"),
            environments=({"environmentId": "local", "cwd": "/tmp/yoke"},),
            service_tier="priority",
            client_user_message_id="client-message-1",
        ),
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
    )

    params = turn_params(thread, session, Turn(prompt="Use app-server fields."), None)

    assert params["permissions"] == ":workspace"
    assert "sandboxPolicy" not in params
    assert params["approvalsReviewer"] == "auto_review"
    assert params["runtimeWorkspaceRoots"] == ["/tmp/yoke", "/tmp/shared"]
    assert params["environments"] == [{"environmentId": "local", "cwd": "/tmp/yoke"}]
    assert params["serviceTier"] == "priority"
    assert params["clientUserMessageId"] == "client-message-1"


def test_turn_params_include_codex_native_permission_options() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options=CodexOptions(
            sandbox=CodexSandbox.WORKSPACE_WRITE,
            approval=CodexApproval.UNTRUSTED,
            network=True,
            writable_roots=("/tmp/yoke", "/tmp/shared"),
        ),
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
    )

    params = turn_params(thread, session, Turn(prompt="Use native permissions."), None)

    assert params["approvalPolicy"] == "untrusted"
    assert params["sandboxPolicy"] == {
        "type": "workspaceWrite",
        "writableRoots": ["/tmp/yoke", "/tmp/shared"],
        "networkAccess": True,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def test_turn_params_preserve_neutral_network_permission() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(access="write", network=True),
        effort=None,
        provider_options={},
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
    )

    params = turn_params(thread, session, Turn(prompt="Use network."), None)

    assert params["sandboxPolicy"]["networkAccess"] is True


def test_turn_params_can_override_thread_provider_options() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options=CodexOptions(
            collaboration={"mode": "default", "settings": {}}
        ),
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
    )

    params = turn_params(
        thread,
        session,
        Turn(prompt="Use collaboration mode."),
        None,
        provider_options=CodexOptions(
            collaboration={"mode": "plan", "settings": {"model": "gpt-5.4-mini"}}
        ),
    )

    assert params["collaborationMode"] == {
        "mode": "plan",
        "settings": {"model": "gpt-5.4-mini"},
    }


def test_experimental_api_requires_experimental_thread() -> None:
    thread = AppServerThread(
        process=None,
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
        experimental_api=False,
    )

    with pytest.raises(YokeError, match="experimentalApi"):
        require_experimental_api(thread, CodexOptions(experimental_api=True))


def test_fork_params_include_codex_app_server_options() -> None:
    session = Session(provider="codex", surface="codex_app_server", id="thread-1")

    params = fork_params(
        session,
        ForkOptions(
            ephemeral=True,
            last_turn_id="turn-1",
            exclude_turns=True,
        ),
    )

    assert params == {
        "threadId": "thread-1",
        "ephemeral": True,
        "lastTurnId": "turn-1",
        "excludeTurns": True,
    }


def test_codex_app_server_fork_thread_parses_thread_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_request_rpc(process, method, params, timeout):
        calls.append((process, method, params, timeout))
        return {"thread": {"id": "thread-fork"}}

    monkeypatch.setattr(
        "yoke.providers.codex_app_server.request_rpc",
        fake_request_rpc,
    )
    adapter = CodexAppServer(rpc_timeout_seconds=12)
    source = AppServerThread(
        process=object(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort="high",
        provider_options={"raw": True},
    )
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(network=True),
    )

    forked = adapter._fork_thread(
        source,
        session,
        ForkOptions(ephemeral=True),
    )

    assert forked.thread_id == "thread-fork"
    assert forked.process is source.process
    assert forked.effort == "high"
    assert forked.provider_options == {"raw": True}
    assert calls == [
        (
            source.process,
            "thread/fork",
            {"threadId": "thread-1", "ephemeral": True},
            12,
        )
    ]


def test_codex_app_server_start_sets_provider_session_id() -> None:
    asyncio.run(run_codex_app_server_start_sets_provider_session_id())


async def run_codex_app_server_start_sets_provider_session_id() -> None:
    adapter = CodexAppServer()
    process = FakeProcess()

    def fake_start_process(cwd):
        return process

    def fake_start_thread(started_process, harness, options, permissions, goal):
        return AppServerThread(
            process=started_process,
            thread_id="thread-1",
            cwd=harness.cwd,
            permissions=permissions,
            effort=None,
            provider_options={},
        )

    adapter._start_process = fake_start_process  # type: ignore[method-assign]
    adapter._start_thread = fake_start_thread  # type: ignore[method-assign]
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
    )

    session = await adapter.start(harness, SessionOptions())

    assert session.id == "thread-1"
    assert session.provider_session_id == "thread-1"


def test_codex_app_server_session_model_survives_into_turn() -> None:
    asyncio.run(run_codex_app_server_session_model_survives_into_turn())


async def run_codex_app_server_session_model_survives_into_turn() -> None:
    adapter = CodexAppServer()
    process = FakeProcess()
    captured: dict[str, object] = {}

    adapter._start_process = lambda cwd: process  # type: ignore[method-assign]

    def fake_start_thread(started_process, harness, options, permissions, goal):
        captured["start_model"] = options.model
        return AppServerThread(
            process=started_process,
            thread_id="thread-1",
            cwd=harness.cwd,
            permissions=permissions,
            effort=None,
            provider_options={},
        )

    def fake_run_turn(thread, session, turn, schema, provider_options, model):
        captured["turn_model"] = model or session.model
        return TurnResult(output="ok")

    adapter._start_thread = fake_start_thread  # type: ignore[method-assign]
    adapter._run_turn = fake_run_turn  # type: ignore[method-assign]
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="root", model="agent-model"),
        cwd=Path("/tmp/yoke"),
    )

    session = await adapter.start(harness, SessionOptions(model="session-model"))
    result = await adapter.send(session, Turn(prompt="test"), RunOptions())

    assert captured == {
        "start_model": "session-model",
        "turn_model": "session-model",
    }
    assert result.requested_model == "session-model"


def test_codex_app_server_run_override_survives_start_and_turn() -> None:
    asyncio.run(run_codex_app_server_run_override_survives_start_and_turn())


async def run_codex_app_server_run_override_survives_start_and_turn() -> None:
    adapter = CodexAppServer()
    process = FakeProcess()
    captured: list[str | None] = []
    adapter._start_process = lambda cwd: process  # type: ignore[method-assign]

    def fake_start_thread(started_process, harness, options, permissions, goal):
        captured.append(options.model)
        return AppServerThread(
            process=started_process,
            thread_id="thread-1",
            cwd=harness.cwd,
            permissions=permissions,
            effort=None,
            provider_options={},
        )

    def fake_run_turn(thread, session, turn, schema, provider_options, model):
        captured.append(model or session.model)
        return TurnResult(output="ok")

    adapter._start_thread = fake_start_thread  # type: ignore[method-assign]
    adapter._run_turn = fake_run_turn  # type: ignore[method-assign]
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="root", model="agent-model"),
        cwd=Path("/tmp/yoke"),
    )

    result = await adapter.run(harness, "test", RunOptions(model="run-model"))

    assert captured == ["run-model", "run-model"]
    assert result.requested_model == "run-model"


def test_codex_app_server_fork_sets_provider_session_id() -> None:
    asyncio.run(run_codex_app_server_fork_sets_provider_session_id())


async def run_codex_app_server_fork_sets_provider_session_id() -> None:
    adapter = CodexAppServer()
    source = AppServerThread(
        process=FakeProcess(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
    )
    adapter._threads["thread-1"] = source

    def fake_fork_thread(source_thread, session, options):
        return AppServerThread(
            process=source_thread.process,
            thread_id="thread-fork",
            cwd=session.cwd,
            permissions=session.permissions,
            effort=source_thread.effort,
            provider_options=source_thread.provider_options,
        )

    adapter._fork_thread = fake_fork_thread  # type: ignore[method-assign]
    session = Session(
        provider="codex",
        surface="codex_app_server",
        id="thread-1",
        agent=Agent(instructions="root"),
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
    )

    forked = await adapter.fork(session, ForkOptions())

    assert forked.id == "thread-fork"
    assert forked.provider_session_id == "thread-fork"


def test_codex_app_server_process_refs_close_after_last_session() -> None:
    adapter = CodexAppServer()
    process = FakeProcess()

    adapter._retain_process(process)
    adapter._retain_process(process)
    adapter._release_process(process)

    assert process.terminated is False

    adapter._release_process(process)

    assert process.terminated is True


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_codex_app_server_interrupt_uses_active_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_request_rpc(process, method, params, timeout):
        calls.append((process, method, params, timeout))
        return {}

    monkeypatch.setattr(
        "yoke.providers.codex_app_server.request_rpc",
        fake_request_rpc,
    )
    adapter = CodexAppServer(rpc_timeout_seconds=12)
    thread = AppServerThread(
        process=object(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
        active_turn_id="turn-1",
    )

    adapter._interrupt(thread)

    assert calls == [
        (
            thread.process,
            "turn/interrupt",
            {"threadId": "thread-1", "turnId": "turn-1"},
            12,
        )
    ]


def test_codex_app_server_interrupt_requires_active_turn() -> None:
    adapter = CodexAppServer()
    thread = AppServerThread(
        process=object(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
    )

    with pytest.raises(YokeError, match="no active turn"):
        adapter._interrupt(thread)


def test_codex_app_server_compact_starts_thread_compaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_request_rpc(process, method, params, timeout):
        calls.append((process, method, params, timeout))
        return {}

    monkeypatch.setattr(
        "yoke.providers.codex_app_server.request_rpc",
        fake_request_rpc,
    )
    adapter = CodexAppServer(rpc_timeout_seconds=12)
    thread = AppServerThread(
        process=object(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
    )

    adapter._compact_thread(thread)

    assert calls == [
        (
            thread.process,
            "thread/compact/start",
            {"threadId": "thread-1"},
            12,
        )
    ]


def test_codex_app_server_rename_live_thread_does_not_reinitialize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_request_rpc(process, method, params, timeout):
        calls.append((process, method, params, timeout))
        if method == "thread/name/set":
            return {"thread": {"id": params["threadId"], "name": params["name"]}}
        return {}

    monkeypatch.setattr(
        "yoke.providers.codex_app_server.request_rpc",
        fake_request_rpc,
    )
    adapter = CodexAppServer(rpc_timeout_seconds=12)
    thread = AppServerThread(
        process=object(),
        thread_id="thread-1",
        cwd=Path("/tmp/yoke"),
        permissions=Permissions(),
        effort=None,
        provider_options={},
    )

    renamed = adapter._rename_thread(thread, "Renamed")

    assert renamed.title == "Renamed"
    assert calls == [
        (
            thread.process,
            "thread/name/set",
            {"threadId": "thread-1", "name": "Renamed"},
            12,
        )
    ]


def test_parse_models_reads_app_server_model_list() -> None:
    models = parse_models(
        {
            "models": [
                {
                    "id": "gpt-5.4-mini",
                    "hidden": False,
                    "supportedReasoningEfforts": [
                        {"reasoningEffort": "low", "description": "Fast"},
                        {"reasoningEffort": "medium", "description": "Balanced"},
                    ],
                },
                {"name": "fallback-name", "hidden": True},
                {"hidden": False},
            ]
        }
    )

    assert [model.id for model in models] == ["gpt-5.4-mini", "fallback-name"]
    assert models[0].reasoning_efforts == ("low", "medium")
    assert models[1].hidden is True
    assert models[0].raw is not None
