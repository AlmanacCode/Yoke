from __future__ import annotations

import json
from pathlib import Path

from yoke import (
    Agent,
    Event,
    EventKind,
    Run,
    RunStatus,
    RunStore,
    Session,
    StepResult,
    WorkflowRun,
)


def test_run_store_records_run_result_events_and_provider_handle(
    tmp_path: Path,
) -> None:
    store = RunStore.at(tmp_path / ".yoke")
    result = Run(
        provider="codex",
        surface="codex_app_server",
        status=RunStatus.SUCCEEDED,
        output="ok",
        events=(
            Event(
                kind=EventKind.PROVIDER_SESSION,
                message="codex provider session thr_123",
                provider_session_id="thr_123",
            ),
            Event(kind=EventKind.TEXT, message="ok"),
        ),
        session=Session(
            provider="codex",
            surface="codex_app_server",
            id="thr_123",
            provider_session_id="thr_123",
            agent=Agent(instructions="Coordinate."),
            cwd=tmp_path,
        ),
    )

    record = store.record(
        result,
        id="run_test",
        agent="codealmanac",
        collection="agents",
    )

    record_json = json.loads((tmp_path / ".yoke/runs/run_test/record.json").read_text())
    result_json = json.loads((tmp_path / ".yoke/runs/run_test/result.json").read_text())
    event_lines = (
        tmp_path / ".yoke/runs/run_test/events.jsonl"
    ).read_text().splitlines()

    assert record.id == "run_test"
    assert record.kind == "run"
    assert record.provider == "codex"
    assert record.surface == "codex_app_server"
    assert record.cwd == tmp_path
    assert record.agent == "codealmanac"
    assert record.collection == Path("agents")
    assert record.provider_session_id == "thr_123"
    assert record.event_count == 2
    assert record_json["provider_session_id"] == "thr_123"
    assert result_json["output"] == "ok"
    assert "events" not in result_json
    assert [json.loads(line)["kind"] for line in event_lines] == [
        "provider_session",
        "text",
    ]


def test_run_store_loads_and_lists_records(tmp_path: Path) -> None:
    store = RunStore.at(tmp_path / ".yoke")
    result = Run(provider="claude", surface="claude_python_sdk", output="ok")

    first = store.record(result, id="run_first")
    second = store.record(result, id="run_second")

    assert store.load("run_first") == first
    assert store.list() == (second, first)


def test_run_store_records_workflow_events(tmp_path: Path) -> None:
    store = RunStore.at(tmp_path / ".yoke")
    step_run = Run(
        provider="codex",
        surface="codex_app_server",
        output="reviewed",
        events=(Event(kind=EventKind.TEXT, message="reviewed"),),
        session=Session(
            provider="codex",
            surface="codex_app_server",
            id="thr_child",
            provider_session_id="thr_child",
        ),
    )
    workflow = WorkflowRun(
        workflow="review",
        provider="codex",
        surface="codex_app_server",
        steps=(
            StepResult(
                step="review",
                agent="reviewer",
                prompt="Review.",
                run=step_run,
            ),
        ),
        output="reviewed",
    )

    record = store.record(workflow, id="run_workflow", cwd=tmp_path)
    event_lines = (
        tmp_path / ".yoke/runs/run_workflow/events.jsonl"
    ).read_text().splitlines()

    assert record.kind == "workflow"
    assert record.provider_session_id == "thr_child"
    assert record.event_count == 1
    assert json.loads(event_lines[0])["message"] == "reviewed"
