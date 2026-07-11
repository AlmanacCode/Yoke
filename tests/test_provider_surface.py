from __future__ import annotations

from pathlib import Path

from yoke import Agent, Channel, Harness, Provider, Session, Surface, adapter_for


def test_harness_accepts_string_provider_and_surface() -> None:
    harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.provider is Provider.CODEX
    assert harness.surface is Surface.CODEX_APP_SERVER
    assert adapter_for(harness.provider, harness.surface).surface == "codex_app_server"


def test_harness_accepts_auto_surface_as_capability_selected() -> None:
    harness = Harness(
        provider="codex",
        surface="auto",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.surface is None
    assert harness.require("readable_goal").surface is Surface.CODEX_APP_SERVER


def test_harness_accepts_provider_surface_aliases() -> None:
    codex = Harness(
        provider="codex",
        surface="app",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )
    claude = Harness(
        provider="claude",
        surface="sdk",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert codex.surface is Surface.CODEX_APP_SERVER
    assert claude.surface is Surface.CLAUDE_PYTHON_SDK


def test_session_accepts_provider_surface_aliases() -> None:
    codex = Session(provider="codex", surface="app", id="thread")
    claude = Session(provider="claude", surface="typescript", id="session")

    assert codex.surface is Surface.CODEX_APP_SERVER
    assert claude.surface is Surface.CLAUDE_TYPESCRIPT_SDK


def test_harness_accepts_enum_provider_and_surface() -> None:
    harness = Harness(
        provider=Provider.CLAUDE,
        surface=Surface.CLAUDE_PYTHON_SDK,
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.provider == "claude"
    assert harness.surface == "claude_python_sdk"
    assert adapter_for(harness.provider, harness.surface).provider == "claude"


def test_surface_enum_tracks_unimplemented_documented_entrypoints() -> None:
    assert Surface.CODEX_PYTHON_SDK == "codex_python_sdk"
    assert Surface.CODEX_TYPESCRIPT_SDK == "codex_typescript_sdk"
    assert Surface.CLAUDE_TYPESCRIPT_SDK == "claude_typescript_sdk"


def test_channel_enum_tracks_exposure_paths() -> None:
    assert Channel.CLI == "cli"
    assert Channel.SDK == "sdk"
    assert Channel.APP_SERVER == "app_server"
