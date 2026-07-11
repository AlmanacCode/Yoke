from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from yoke import Agent, Harness, RunOptions, Session, Skill
from yoke.options import ForkOptions, SessionOptions
from yoke.providers.claude import Claude


def sdk_module(*, query_error: bool = False, connect_error: bool = False):
    module = SimpleNamespace()

    class Options:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Definition:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Client:
        def __init__(self, options):
            self.options = options

        async def connect(self):
            module.plugin_path = Path(self.options.kwargs["plugins"][0]["path"])
            module.plugin_paths.append(module.plugin_path)
            if connect_error:
                raise RuntimeError("connect failed")

        async def disconnect(self):
            pass

    async def query(prompt, options):
        module.plugin_path = Path(options.kwargs["plugins"][0]["path"])
        if query_error:
            raise RuntimeError("query failed")
        yield SimpleNamespace(subtype="success", result="ok", session_id="session")

    module.AgentDefinition = Definition
    module.ClaudeAgentOptions = Options
    module.ClaudeSDKClient = Client
    module.query = query
    module.plugin_paths = []
    return module


def harness(tmp_path: Path) -> Harness:
    return Harness(
        provider="claude",
        agent=Agent(
            instructions="parent",
            skills=(Skill.from_text("native", name="native"),),
        ),
        cwd=tmp_path / "workspace",
        runtime_root=tmp_path / "runtime",
    )


@pytest.mark.asyncio
async def test_claude_one_shot_cleans_runtime_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)

    await Claude().run(harness(tmp_path), "work", RunOptions())

    assert not module.plugin_path.exists()


@pytest.mark.asyncio
async def test_claude_one_shot_cleans_runtime_on_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module(query_error=True)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)

    with pytest.raises(RuntimeError, match="query failed"):
        await Claude().run(harness(tmp_path), "work", RunOptions())

    assert not module.plugin_path.exists()


@pytest.mark.asyncio
async def test_claude_live_cleans_on_close_and_connect_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    adapter = Claude()
    session = await adapter.start(harness(tmp_path), SessionOptions())
    assert module.plugin_path.exists()
    await adapter.close(session)
    assert not module.plugin_path.exists()

    failing = sdk_module(connect_error=True)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", failing)
    with pytest.raises(RuntimeError, match="connect failed"):
        await Claude().start(harness(tmp_path), SessionOptions())
    assert not failing.plugin_path.exists()


@pytest.mark.asyncio
async def test_claude_fork_preserves_live_runtime_parent_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    adapter = Claude()
    source = await adapter.start(harness(tmp_path), SessionOptions())
    source = source.model_copy(update={"provider_session_id": "provider-session"})

    forked = await adapter.fork(source, ForkOptions())
    source_plugin, fork_plugin = module.plugin_paths
    runtime_root = (tmp_path / "runtime").resolve()
    assert source_plugin.is_relative_to(runtime_root)
    assert fork_plugin.is_relative_to(runtime_root)
    assert source_plugin != fork_plugin

    await adapter.close(forked)
    assert source_plugin.exists()
    assert not fork_plugin.exists()
    await adapter.close(source)
    assert not source_plugin.exists()


@pytest.mark.asyncio
async def test_claude_non_live_fork_uses_persisted_runtime_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    request = harness(tmp_path)
    source = Session(
        provider="claude",
        surface="claude_python_sdk",
        id="closed-local-session",
        provider_session_id="provider-session",
        agent=request.agent,
        cwd=request.cwd,
        runtime_root=request.runtime_root,
    )
    assert "runtime_root" not in source.model_dump()
    assert str(request.runtime_root) not in repr(source)

    adapter = Claude()
    forked = await adapter.fork(source, ForkOptions())
    fork_plugin = module.plugin_paths[-1]
    assert fork_plugin.is_relative_to(request.runtime_root.resolve())
    assert forked.runtime_root == request.runtime_root
    await adapter.close(forked)
    assert not fork_plugin.exists()


@pytest.mark.asyncio
async def test_claude_duplicate_resume_sessions_are_isolated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    adapter = Claude()
    request = harness(tmp_path)

    first = await adapter.start(request, SessionOptions(resume="provider-session"))
    second = await adapter.start(request, SessionOptions(resume="provider-session"))
    first_plugin, second_plugin = module.plugin_paths
    assert first.id != second.id
    assert first.provider_session_id == second.provider_session_id == "provider-session"

    await adapter.close(first)
    assert not first_plugin.exists()
    assert second_plugin.exists()
    await adapter.close(second)
    assert not second_plugin.exists()
