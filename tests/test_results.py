from __future__ import annotations

import pytest

from yoke import Event, Failure, Run, RunStatus, Session, Surface, WorkflowRun
from yoke.errors import YokeError


def test_run_ok_and_raise_for_status_success() -> None:
    run = Run(provider="codex")

    assert run.ok is True
    assert run.raise_for_status() is run


def test_run_tracks_surface() -> None:
    run = Run(provider="codex", surface="codex_app_server")

    assert run.surface is Surface.CODEX_APP_SERVER


def test_run_raise_for_status_failure() -> None:
    run = Run(
        provider="codex",
        status=RunStatus.FAILED,
        failure=Failure(message="bad output", code="invalid_structured_output"),
    )

    assert run.ok is False
    with pytest.raises(YokeError, match=r"invalid_structured_output"):
        run.raise_for_status()


def test_run_exposes_provider_session_id_from_session() -> None:
    run = Run(
        provider="claude",
        session=Session(
            provider="claude",
            surface="claude_python_sdk",
            id="local-session",
            provider_session_id="provider-session",
        ),
        events=(Event(kind="provider_session", provider_session_id="event-session"),),
    )

    assert run.provider_session_id == "provider-session"
    assert run.model_dump()["provider_session_id"] == "provider-session"


def test_run_exposes_provider_session_id_from_events() -> None:
    run = Run(
        provider="codex",
        events=(
            Event(kind="text", message="hello"),
            Event(kind="provider_session", provider_session_id="thread-1"),
        ),
    )

    assert run.provider_session_id == "thread-1"
    assert run.model_dump()["provider_session_id"] == "thread-1"


def test_workflow_run_ok_and_raise_for_status() -> None:
    success = WorkflowRun(workflow="review")
    failure = WorkflowRun(
        workflow="review",
        status=RunStatus.FAILED,
        failure=Failure(message="review failed"),
    )

    assert success.ok is True
    assert success.raise_for_status() is success
    assert failure.ok is False
    with pytest.raises(YokeError, match="review failed"):
        failure.raise_for_status()
