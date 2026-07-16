from __future__ import annotations

from pathlib import Path

from yoke import Agent, Channel, Harness, Provider, Session, Surface, adapter_for
from yoke.surfaces import report_for


def test_harness_accepts_opencode_provider_and_surface() -> None:
    harness = Harness(
        provider="opencode",
        surface="opencode_server",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.provider is Provider.OPENCODE
    assert harness.surface is Surface.OPENCODE_SERVER
    assert adapter_for(harness.provider, harness.surface).surface == "opencode_server"


def test_harness_accepts_opencode_surface_aliases() -> None:
    for alias in ("server", "app", "app_server", "http"):
        harness = Harness(
            provider="opencode",
            surface=alias,
            agent=Agent(instructions="test"),
            cwd=Path.cwd(),
        )
        assert harness.surface is Surface.OPENCODE_SERVER


def test_session_accepts_opencode_provider_surface() -> None:
    session = Session(provider="opencode", surface="app", id="abc")

    assert session.provider is Provider.OPENCODE
    assert session.surface is Surface.OPENCODE_SERVER


def test_opencode_default_surface_resolves_without_explicit_surface() -> None:
    harness = Harness(
        provider="opencode",
        agent=Agent(instructions="test"),
        cwd=Path.cwd(),
    )

    assert harness.surface is None
    assert harness.require("models").surface is Surface.OPENCODE_SERVER


def test_opencode_surface_report_is_app_server_channel_and_runnable() -> None:
    report = report_for(Provider.OPENCODE, Surface.OPENCODE_SERVER)

    assert report.channel == str(Channel.APP_SERVER)
    assert report.runnable is True
    features = {row.feature: row.support for row in report.features}
    assert features["session"] == "native"
    assert features["streaming"] == "emulated"
    assert features["request_events"] == "compiled"
