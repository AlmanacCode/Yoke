from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import ValidationError

from yoke import (
    Agent,
    Authentication,
    AuthMethod,
    Credentials,
    Discovery,
    Feature,
    Harness,
    Login,
    UnsupportedFeature,
    clear_adapters,
    discover,
    profile_for,
    register,
)
from yoke.providers import claude as claude_provider
from yoke.providers.claude import Claude, claude_options, credential_env
from yoke.providers.codex_app_server import CodexAppServer, codex_login_auth_method
from yoke.providers.codex_sdk import CodexPythonSdk, codex_auth_method
from yoke.readiness import CommandCheck


def harness(provider: str, surface: str, credentials: Credentials) -> Harness:
    return Harness(
        provider=provider,
        surface=surface,
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
        credentials=credentials,
    )


def test_credentials_are_runtime_only_and_redacted() -> None:
    value = harness(
        "claude",
        "claude_python_sdk",
        Credentials.api_key("sentinel-secret"),
    )

    assert "sentinel-secret" not in repr(value)
    assert "sentinel-secret" not in value.model_dump_json()
    assert "credentials" not in value.model_dump()


@pytest.mark.asyncio
async def test_login_runtime_handle_is_never_represented_or_serialized() -> None:
    sentinel = "provider-login-secret"

    class Handle:
        def __repr__(self) -> str:
            return sentinel

        async def wait(self):
            return SimpleNamespace(
                success=True,
                message="authenticated",
                token=sentinel,
            )

    pending = Login(provider="codex", method="device_code", raw=Handle())
    completed = await pending.wait()

    for value in (pending, completed):
        assert sentinel not in repr(value)
        assert sentinel not in value.model_dump_json()
        assert "raw" not in value.model_dump()


@pytest.mark.parametrize("factory", [Credentials.api_key, Credentials.oauth_token])
def test_invalid_credentials_never_echo_input(factory) -> None:
    secret = " secret-that-must-never-leak "
    assert factory(secret).reveal() == secret.strip()

    with pytest.raises(ValidationError) as raised:
        factory("   ")

    assert "input_value" not in str(raised.value)

    with pytest.raises(ValidationError) as mismatched:
        Credentials(method=AuthMethod.EXTERNAL, secret="leak-sentinel")
    assert "leak-sentinel" not in str(mismatched.value)
    assert "input_value" not in str(mismatched.value)


def test_claude_credentials_reach_sdk_env_without_losing_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Options:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module = ModuleType("claude_agent_sdk")
    module.ClaudeAgentOptions = Options
    module.AgentDefinition = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    monkeypatch.setenv("YOKE_KEEP_ME", "present")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "process-token")
    value = harness(
        "claude",
        "claude_python_sdk",
        Credentials.oauth_token("sentinel-oauth"),
    )

    options = claude_options(value, SimpleNamespace(
        resolve_goal=lambda goal: goal,
        model=None,
        effort=None,
        max_turns=None,
        permissions=None,
        provider=None,
        output_schema=None,
    ))

    assert options.kwargs["env"]["YOKE_KEEP_ME"] == "present"
    assert options.kwargs["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "sentinel-oauth"
    assert credential_env(
        value, {"CLAUDE_CODE_OAUTH_TOKEN": "adapter-token"}
    )["CLAUDE_CODE_OAUTH_TOKEN"] == "sentinel-oauth"


@pytest.mark.asyncio
async def test_claude_auth_status_reports_direct_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", ModuleType("claude_agent_sdk"))
    value = harness(
        "claude",
        "claude_python_sdk",
        Credentials.api_key("sentinel-secret"),
    ).with_adapter(Claude())

    status = await value.auth_status()

    assert status.authenticated is None
    assert status.compatible is None
    assert status.live_tested is False
    assert status.method is AuthMethod.API_KEY
    assert AuthMethod.OAUTH_TOKEN in status.methods
    assert "sentinel" not in status.model_dump_json()


@pytest.mark.asyncio
async def test_existing_claude_oauth_is_discovered_without_a_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", ModuleType("claude_agent_sdk"))

    async def fake_run_command(*args, env=None):
        return CommandCheck(
            code=0,
            stdout='{"loggedIn":true,"authMethod":"claude.ai"}',
            stderr="",
        )

    monkeypatch.setattr(claude_provider, "run_command", fake_run_command)
    value = harness("claude", "claude_python_sdk", Credentials.auto()).with_adapter(
        Claude()
    )

    status = await value.auth_status()

    assert status.installed and status.authenticated
    assert status.compatible is None
    assert status.method is AuthMethod.EXTERNAL


@pytest.mark.asyncio
async def test_logged_out_claude_json_has_readable_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", ModuleType("claude_agent_sdk"))

    async def fake_run_command(*args, env=None):
        return CommandCheck(
            code=1,
            stdout='{"loggedIn":false,"authMethod":"none"}',
            stderr="",
        )

    monkeypatch.setattr(claude_provider, "run_command", fake_run_command)
    value = harness("claude", "claude_python_sdk", Credentials.auto()).with_adapter(
        Claude()
    )

    readiness = await value.check()

    assert readiness.available is False
    assert readiness.message == "Claude not logged in"
    assert readiness.fix == "Run `claude auth login` or provide Claude credentials."


@pytest.mark.asyncio
async def test_codex_sdk_rejects_runtime_key_without_persisting_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace()

    class Client:
        def __init__(self, config=None):
            self.login_values = []
            module.clients = [*getattr(module, "clients", []), self]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def login_api_key(self, value):
            self.login_values.append(value)

        async def account(self, **kwargs):
            return SimpleNamespace(account=SimpleNamespace(type="apiKey"))

        async def models(self):
            return SimpleNamespace(data=[])

        async def thread_start(self, **kwargs):
            return SimpleNamespace(id="thread-1")

    module.AsyncCodex = Client
    module.__version__ = "test"
    module.ApprovalMode = SimpleNamespace(deny_all="deny", auto_review="auto")
    module.Sandbox = SimpleNamespace(
        full_access="full", workspace_write="write", read_only="read"
    )
    monkeypatch.setitem(sys.modules, "openai_codex", module)
    monkeypatch.setattr("yoke.providers.codex_sdk.shutil.which", lambda _: "/bin/codex")

    async def fake_command(*args, **kwargs):
        return CommandCheck(code=0, stdout="codex 1", stderr="")

    monkeypatch.setattr("yoke.providers.codex_sdk.run_command", fake_command)
    value = harness(
        "codex", "codex_python_sdk", Credentials.api_key("sentinel-key")
    ).with_adapter(CodexPythonSdk(codex_bin="/bin/codex"))

    status = await value.auth_status()

    assert status.ready is False
    assert status.compatible is None
    assert not hasattr(module, "clients")
    with pytest.raises(UnsupportedFeature, match="persist provider state"):
        await value.models()
    with pytest.raises(UnsupportedFeature, match="persist provider state"):
        await value.start()
    assert not hasattr(module, "clients")
    assert value.auth_methods() == (AuthMethod.EXTERNAL,)
    assert value.login_methods() == (
        AuthMethod.API_KEY,
        AuthMethod.CHATGPT,
        AuthMethod.DEVICE_CODE,
    )

    async def broken_account(self, **kwargs):
        raise RuntimeError("provider-secret-detail")

    Client.account = broken_account
    external = harness(
        "codex", "codex_python_sdk", Credentials.auto()
    ).with_adapter(CodexPythonSdk(codex_bin="/bin/codex"))
    unknown = await external.auth_status()
    assert unknown.compatible is None
    assert unknown.authenticated is False
    assert "provider-secret-detail" not in unknown.model_dump_json()


@pytest.mark.asyncio
async def test_codex_sdk_auth_status_discovers_persisted_api_key_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace()

    class Client:
        def __init__(self, config=None):
            self.login_values = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def login_api_key(self, value):
            self.login_values.append(value)

        async def account(self, **kwargs):
            return SimpleNamespace(
                account=SimpleNamespace(
                    root=SimpleNamespace(type="apiKey"),
                ),
                requires_openai_auth=True,
            )

    module.AsyncCodex = Client
    module.__version__ = "0.1.0b2"
    module.ApprovalMode = SimpleNamespace(deny_all="deny", auto_review="auto")
    module.Sandbox = SimpleNamespace(
        full_access="full", workspace_write="write", read_only="read"
    )
    monkeypatch.setitem(sys.modules, "openai_codex", module)

    async def fake_command(*args, **kwargs):
        return CommandCheck(code=0, stdout="codex 1", stderr="")

    monkeypatch.setattr("yoke.providers.codex_sdk.run_command", fake_command)
    value = harness(
        "codex", "codex_python_sdk", Credentials.auto()
    ).with_adapter(CodexPythonSdk(codex_bin="/bin/codex"))

    login = await value.login(AuthMethod.API_KEY, api_key="sentinel-key")
    status = await value.auth_status()

    assert login.success is True
    assert login.method is AuthMethod.API_KEY
    assert status.ready is True
    assert status.authenticated is True
    assert status.method is AuthMethod.API_KEY
    assert status.methods == (
        AuthMethod.EXTERNAL,
        AuthMethod.API_KEY,
        AuthMethod.CHATGPT,
        AuthMethod.DEVICE_CODE,
    )
    assert "sentinel-key" not in status.model_dump_json()


def test_oauth_token_is_honestly_unavailable_for_codex_sdk() -> None:
    value = harness(
        "codex", "codex_python_sdk", Credentials.oauth_token("sentinel-oauth")
    )

    assert AuthMethod.OAUTH_TOKEN not in value.auth_methods()


@pytest.mark.parametrize(
    ("account_type", "expected"),
    [
        ("apiKey", AuthMethod.API_KEY),
        ("chatgpt", AuthMethod.CHATGPT),
        ("amazonBedrock", AuthMethod.EXTERNAL),
    ],
)
def test_codex_sdk_maps_persisted_account_types(
    account_type: str,
    expected: AuthMethod,
) -> None:
    response = {"account": {"type": account_type}}

    assert codex_auth_method(response) is expected


def test_codex_sdk_missing_account_has_no_auth_method() -> None:
    assert codex_auth_method({"account": None}) is None


@pytest.mark.asyncio
async def test_codex_app_auth_status_discovers_persisted_api_key_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_command(*args, **kwargs):
        return CommandCheck(
            code=0,
            stdout="Logged in using an API key - sk-proj-***safe",
            stderr="",
        )

    monkeypatch.setattr("yoke.providers.codex_app_server.run_command", fake_command)
    value = harness(
        "codex", "codex_app_server", Credentials.auto()
    ).with_adapter(CodexAppServer())

    status = await value.auth_status()

    assert status.ready is True
    assert status.authenticated is True
    assert status.method is AuthMethod.API_KEY
    assert status.methods == (
        AuthMethod.EXTERNAL,
        AuthMethod.API_KEY,
        AuthMethod.CHATGPT,
    )
    assert "sk-proj" not in status.model_dump_json()


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Logged in using an API key - sk-***safe", AuthMethod.API_KEY),
        ("Logged in using ChatGPT", AuthMethod.CHATGPT),
        ("Codex authenticated", AuthMethod.EXTERNAL),
    ],
)
def test_codex_app_maps_cli_login_status(
    message: str,
    expected: AuthMethod,
) -> None:
    assert codex_login_auth_method(message) is expected


def test_discovery_reuses_capability_selection_and_keeps_credentials_private() -> None:
    found = Discovery(
        provider="codex",
        cwd=Path.cwd(),
        agent=Agent(instructions="test"),
        credentials=Credentials.auto(),
        surfaces=(),
    )

    with pytest.raises(UnsupportedFeature, match="no discovered ready"):
        found.harness(Feature.STREAMING)
    assert "credentials" not in found.model_dump()


def test_discovery_without_agent_only_requires_it_when_building_harness() -> None:
    found = Discovery(provider="claude", cwd=Path.cwd(), surfaces=())

    with pytest.raises(ValueError, match="pass agent"):
        found.harness()


@pytest.mark.asyncio
async def test_discover_probes_auth_once_dedupes_and_selects_ready_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_module = importlib.import_module("yoke.discovery")
    app_profile = profile_for("codex", "codex_app_server")
    sdk_profile = profile_for("codex", "codex_python_sdk")

    class FakeAdapter:
        provider = "codex"
        capabilities = None

        def __init__(self, surface: str, ready: bool):
            self.surface = surface
            self.ready = ready
            self.auth_calls = 0
            self.check_calls = 0
            self.model_calls = 0

        async def auth_status(self, harness):
            self.auth_calls += 1
            return Authentication(
                provider="codex",
                surface=self.surface,
                methods=(AuthMethod.EXTERNAL,),
                method=AuthMethod.EXTERNAL if self.ready else None,
                installed=True,
                authenticated=self.ready,
                compatible=None,
                ready=self.ready,
                live_tested=False,
                message="ready" if self.ready else "not authenticated",
            )

        async def check(self, harness):
            self.check_calls += 1
            raise AssertionError("discover must derive readiness from auth status")

        async def models(self, harness):
            self.model_calls += 1
            return ()

    unavailable = FakeAdapter("codex_app_server", False)
    ready = FakeAdapter("codex_python_sdk", True)
    clear_adapters()
    register(unavailable)
    register(ready)
    monkeypatch.setattr(
        discovery_module,
        "profiles_for",
        lambda *args, **kwargs: (app_profile, app_profile, sdk_profile),
    )
    try:
        found = await discover("codex", Path.cwd())
        assert found.agent is None
        selected = found.model_copy(
            update={"agent": Agent(instructions="test")}
        ).harness(Feature.STREAMING)
    finally:
        clear_adapters()

    assert len(found.surfaces) == 2
    assert unavailable.auth_calls == 1
    assert ready.auth_calls == 1
    assert unavailable.check_calls == ready.check_calls == 0
    assert selected.surface == "codex_python_sdk"
