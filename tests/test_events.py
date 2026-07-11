from __future__ import annotations

from yoke import AgentCall, Event, EventKind, Surface


def test_known_event_kind_is_typed_enum() -> None:
    event = Event(kind="tool_use", message="running command")

    assert event.kind is EventKind.TOOL_USE
    assert event.kind == "tool_use"


def test_unknown_provider_event_kind_stays_string() -> None:
    event = Event(kind="provider/custom", message="custom")

    assert event.kind == "provider/custom"


def test_event_tracks_surface() -> None:
    event = Event(kind="text", surface="codex_app_server", message="hello")

    assert event.surface is Surface.CODEX_APP_SERVER


def test_event_text_is_readable_message_alias() -> None:
    event = Event(kind="text_delta", message="hello")

    assert event.text == "hello"


def test_event_can_carry_provider_native_agent_activity() -> None:
    event = Event(
        kind="tool_result",
        agent=AgentCall(action="spawnAgent", receiver_thread_ids=("child",)),
    )

    assert event.agent is not None
    assert event.agent.action == "spawnAgent"
    assert event.agent.receiver_thread_ids == ("child",)
