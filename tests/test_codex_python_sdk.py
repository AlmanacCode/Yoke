from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from yoke import (
    Access,
    Agent,
    AuthMethod,
    EventKind,
    Goal,
    Harness,
    Permissions,
    Provider,
    RunOptions,
    Surface,
    Turn,
    adapter_for,
)
from yoke.providers.codex_sdk import CodexPythonSdk, sdk_event, sdk_events, usage_dict


class Summary(BaseModel):
    summary: str


def test_codex_python_sdk_surface_routes_to_sdk_adapter() -> None:
    adapter = adapter_for(Provider.CODEX, Surface.CODEX_PYTHON_SDK)

    assert adapter.surface == "codex_python_sdk"


def test_codex_python_sdk_unknown_stream_event_keeps_neutral_kind() -> None:
    raw = SimpleNamespace(method="thread/customThing")

    event = sdk_event(raw)

    assert event.kind is EventKind.STREAM_EVENT
    assert event.message == "thread/customThing"
    assert event.raw is raw


def test_codex_python_sdk_reuses_app_server_text_delta_mapping() -> None:
    raw = SimpleNamespace(
        method="item/agentMessage/delta",
        params={
            "threadId": "thread-1",
            "turnId": "turn-1",
            "delta": "hello",
        },
    )

    events = sdk_events(raw)

    assert len(events) == 1
    event = events[0]
    assert event.kind is EventKind.TEXT_DELTA
    assert event.text == "hello"
    assert event.source_thread_id == "thread-1"
    assert event.source_turn_id == "turn-1"


def test_codex_python_sdk_reuses_app_server_rate_limit_mapping() -> None:
    raw = SimpleNamespace(
        method="account/rateLimits/updated",
        params={"rateLimits": {"primary": {"usedPercent": 25}}},
    )

    event = sdk_event(raw)

    assert event.kind is EventKind.RATE_LIMIT
    assert event.message == "rate limits updated"


def test_codex_python_sdk_usage_object_keeps_reasoning_tokens() -> None:
    usage = usage_dict(
        SimpleNamespace(
            input_tokens=10,
            cached_input_tokens=4,
            output_tokens=6,
            reasoning_output_tokens=2,
            total_tokens=16,
        )
    )

    assert usage is not None
    assert usage["reasoning_output_tokens"] == 2


@pytest.mark.asyncio
async def test_codex_python_sdk_readiness_reports_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "openai_codex", None)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(CodexPythonSdk())

    readiness = await harness.check()

    assert not readiness.available
    assert readiness.message == "openai_codex is not installed"
    assert (
        readiness.fix
        == "Install Codex SDK support with `pip install almanac-yoke[codex]`."
    )


def test_codex_python_sdk_config_uses_existing_codex_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setattr(
        "yoke.providers.codex_sdk.shutil.which",
        lambda name: "/bin/codex",
    )

    config = CodexPythonSdk()._codex_config(fake)

    assert config.codex_bin == "/bin/codex"


@pytest.mark.asyncio
async def test_codex_python_sdk_runs_thread_with_sdk_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    agent = Agent(
        instructions="You are the root maintainer.",
        goal=Goal("Ship safely."),
        model="gpt-5.4-mini",
        permissions=Permissions(access=Access.WRITE),
    )
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=agent,
        cwd=Path("/tmp/yoke"),
    ).with_adapter(CodexPythonSdk())

    result = await harness.run(
        "Implement it.",
        RunOptions(output_schema=Summary),
    )

    assert result.ok
    assert result.surface == "codex_python_sdk"
    assert result.events[0].surface == "codex_python_sdk"
    assert result.output == '{"summary":"ok"}'
    assert result.data == Summary(summary="ok")
    assert result.requested_model == "gpt-5.4-mini"
    assert result.session is not None
    assert result.session.id == "thread-1"
    assert fake.last_client.thread_start_kwargs["cwd"] == "/tmp/yoke"
    assert fake.last_client.thread_start_kwargs["developer_instructions"] == (
        "You are the root maintainer."
    )
    assert fake.last_client.thread_start_kwargs["ephemeral"] is False
    assert fake.last_client.thread_start_kwargs["model"] == "gpt-5.4-mini"
    assert fake.last_client.thread_start_kwargs["sandbox"] == "workspace_write"
    assert "Goal: Ship safely." in fake.last_thread.run_kwargs["input"]
    assert fake.last_thread.run_kwargs["cwd"] == "/tmp/yoke"
    assert fake.last_thread.run_kwargs["output_schema"]["type"] == "object"
    assert fake.last_client.closed


@pytest.mark.asyncio
async def test_codex_python_sdk_run_override_reaches_thread_and_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path("/tmp/yoke"),
    ).with_adapter(CodexPythonSdk())

    await harness.run("Use the override.", RunOptions(model="run-model"))

    assert fake.last_client.thread_start_kwargs["model"] == "run-model"
    assert fake.last_thread.run_kwargs["model"] == "run-model"


@pytest.mark.asyncio
async def test_codex_python_sdk_session_and_turn_model_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test", model="agent-model"),
        cwd=Path("/tmp/yoke"),
    ).with_adapter(CodexPythonSdk())

    session = await harness.start({"model": "session-model"})
    await session.run("Use session model.")
    assert fake.last_thread.run_kwargs["model"] == "session-model"

    await session.run("Use turn model.", RunOptions(model="turn-model"))
    assert fake.last_thread.run_kwargs["model"] == "turn-model"
    await session.close()


@pytest.mark.asyncio
async def test_codex_python_sdk_parses_typed_model_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    fake.model_response = SimpleNamespace(
        data=[
            SimpleNamespace(
                id="gpt-test",
                hidden=False,
                supportedReasoningEfforts=[
                    SimpleNamespace(reasoningEffort="high")
                ],
            )
        ]
    )
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(CodexPythonSdk())

    models = await harness.models()

    assert [model.id for model in models] == ["gpt-test"]
    assert models[0].reasoning_efforts == ("high",)


def test_codex_python_sdk_parses_snake_case_pydantic_model_fields() -> None:
    class TypedEffort(BaseModel):
        reasoning_effort: str

    class TypedModel(BaseModel):
        id: str
        hidden: bool = False
        supported_reasoning_efforts: list[TypedEffort]

    from yoke.providers.codex_sdk import parse_model

    model = parse_model(
        TypedModel(
            id="gpt-typed",
            supported_reasoning_efforts=[TypedEffort(reasoning_effort="xhigh")],
        )
    )

    assert model is not None
    assert model.id == "gpt-typed"
    assert model.reasoning_efforts == ("xhigh",)


def test_codex_python_sdk_retains_camel_case_model_mapping_compatibility() -> None:
    from yoke.providers.codex_sdk import parse_model

    model = parse_model(
        {
            "id": "gpt-wire",
            "supportedReasoningEfforts": [{"reasoningEffort": "medium"}],
        }
    )

    assert model is not None
    assert model.reasoning_efforts == ("medium",)


@pytest.mark.asyncio
async def test_codex_python_sdk_forks_live_thread_with_shared_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="You are the root maintainer."),
        cwd=Path("/tmp/yoke"),
    ).with_adapter(CodexPythonSdk())

    session = await harness.start()
    forked = await session.fork()

    assert forked.id == "thread-fork"
    assert forked.surface == "codex_python_sdk"
    assert fake.last_client.thread_fork_kwargs["thread_id"] == "thread-1"
    assert fake.last_client.thread_fork_kwargs["cwd"] == "/tmp/yoke"
    assert fake.last_client.thread_fork_kwargs["developer_instructions"] == (
        "You are the root maintainer."
    )

    await session.close()
    assert not fake.last_client.closed
    await forked.close()
    assert fake.last_client.closed


@pytest.mark.asyncio
async def test_codex_python_sdk_interrupts_active_streamed_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    adapter = CodexPythonSdk()
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="You are the root maintainer."),
        cwd=Path("/tmp/yoke"),
    ).with_adapter(adapter)
    session = await harness.start()

    async def consume() -> list[str]:
        return [
            str(event.kind)
            async for event in adapter.stream(
                session,
                Turn(prompt="Wait."),
                RunOptions(),
            )
        ]

    task = asyncio.create_task(consume())
    await fake.last_thread.turn_ready.wait()
    await fake.last_thread.turn_handle.started.wait()
    await session.interrupt()
    fake.last_thread.turn_handle.release.set()

    assert await task == ["stream_event", "stream_event"]
    assert fake.last_thread.turn_handle.interrupted


@pytest.mark.asyncio
async def test_codex_python_sdk_api_key_login_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(CodexPythonSdk())

    login = await harness.login(AuthMethod.API_KEY, api_key="sk-test")

    assert login.success is True
    assert login.message == "Codex API key login completed"
    assert fake.last_client.api_key == "sk-test"
    assert fake.last_client.closed


@pytest.mark.asyncio
async def test_codex_python_sdk_chatgpt_login_waits_on_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(CodexPythonSdk())

    login = await harness.login("chatgpt")
    completed = await login.wait()

    assert login.auth_url == "https://login.example.test"
    assert login.success is None
    assert completed.success is True
    assert fake.last_client.closed


@pytest.mark.asyncio
async def test_codex_python_sdk_device_login_returns_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_openai_codex()
    monkeypatch.setitem(sys.modules, "openai_codex", fake)
    harness = Harness(
        provider="codex",
        surface="codex_python_sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    ).with_adapter(CodexPythonSdk())

    login = await harness.login("device_code")

    assert login.verification_url == "https://device.example.test"
    assert login.user_code == "ABCD-EFGH"


def fake_openai_codex() -> SimpleNamespace:
    module = SimpleNamespace()

    class FakeAsyncCodex:
        def __init__(self, config=None):
            self.config = config
            self.thread_start_kwargs = {}
            self.closed = False
            module.last_client = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            self.closed = True

        async def login_api_key(self, api_key):
            self.api_key = api_key

        async def login_chatgpt(self):
            return FakeLoginHandle(auth_url="https://login.example.test")

        async def login_chatgpt_device_code(self):
            return FakeLoginHandle(
                verification_url="https://device.example.test",
                user_code="ABCD-EFGH",
            )

        async def models(self):
            return getattr(module, "model_response", SimpleNamespace(data=[]))

        async def thread_start(self, **kwargs):
            self.thread_start_kwargs = kwargs
            thread = FakeThread()
            module.last_thread = thread
            return thread

        async def thread_fork(self, thread_id, **kwargs):
            self.thread_fork_kwargs = {"thread_id": thread_id, **kwargs}
            return FakeThread(id="thread-fork")

    class FakeThread:
        def __init__(self, id="thread-1"):
            self.id = id
            self.turn_ready = asyncio.Event()

        async def run(self, input, **kwargs):
            self.run_kwargs = {"input": input, **kwargs}
            return SimpleNamespace(
                final_response='{"summary":"ok"}',
                status=SimpleNamespace(value="completed"),
                error=None,
                usage={"input_tokens": 1, "output_tokens": 2},
            )

        async def turn(self, input, **kwargs):
            self.turn_kwargs = {"input": input, **kwargs}
            self.turn_handle = FakeTurnHandle()
            self.turn_ready.set()
            return self.turn_handle

    class FakeTurnHandle:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.interrupted = False

        async def stream(self):
            self.started.set()
            yield SimpleNamespace(method="turn/started")
            await self.release.wait()
            yield SimpleNamespace(method="turn/completed")

        async def interrupt(self):
            self.interrupted = True

    class FakeLoginHandle:
        def __init__(
            self,
            *,
            auth_url=None,
            verification_url=None,
            user_code=None,
        ):
            self.auth_url = auth_url
            self.verification_url = verification_url
            self.user_code = user_code

        async def wait(self):
            return SimpleNamespace(success=True, message="completed")

    module.AsyncCodex = FakeAsyncCodex
    module.ApprovalMode = SimpleNamespace(
        deny_all="deny_all",
        auto_review="auto_review",
    )
    module.Sandbox = SimpleNamespace(
        read_only="read_only",
        workspace_write="workspace_write",
        full_access="full_access",
    )

    class FakeCodexConfig:
        def __init__(self, codex_bin=None):
            self.codex_bin = codex_bin

    module.CodexConfig = FakeCodexConfig
    module.__version__ = "0.1-test"
    return module
