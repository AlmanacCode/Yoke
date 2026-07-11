"""Inspectable local run storage for Yoke results."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from yoke.models import Event, Run, WorkflowRun, YokeModel

RUN_RECORD_FILE = "record.json"
RUN_RESULT_FILE = "result.json"
RUN_EVENTS_FILE = "events.jsonl"


class RunRecord(YokeModel):
    """Metadata for one stored Yoke run."""

    id: str
    kind: Literal["run", "workflow"]
    created_at: str
    provider: str
    surface: str | None = None
    status: str
    cwd: Path | None = None
    agent: str | None = None
    collection: Path | None = None
    provider_session_id: str | None = None
    provider_turn_id: str | None = None
    run_dir: Path
    result_path: Path
    events_path: Path | None = None
    event_count: int = 0


class RunStore(YokeModel):
    """A `.yoke/runs` store rooted in a project or deployment directory."""

    root: Path = Path(".yoke")

    @classmethod
    def at(cls, path: str | Path = ".yoke") -> RunStore:
        """Return a store rooted at `path`."""

        return cls(root=Path(path))

    @property
    def runs_dir(self) -> Path:
        """Directory containing run records."""

        return self.root / "runs"

    def record(
        self,
        result: Run | WorkflowRun,
        *,
        id: str | None = None,
        agent: str | None = None,
        collection: str | Path | None = None,
        cwd: str | Path | None = None,
    ) -> RunRecord:
        """Persist one run or workflow result and return its record."""

        run_id = id or new_run_id()
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        if isinstance(result, WorkflowRun):
            record = self.record_workflow(
                run_id,
                run_dir,
                result,
                agent=agent,
                collection=collection,
                cwd=cwd,
            )
        else:
            record = self.record_run(
                run_id,
                run_dir,
                result,
                agent=agent,
                collection=collection,
                cwd=cwd,
            )
        write_json(run_dir / RUN_RECORD_FILE, record.model_dump(mode="json"))
        return record

    def record_run(
        self,
        run_id: str,
        run_dir: Path,
        result: Run,
        *,
        agent: str | None,
        collection: str | Path | None,
        cwd: str | Path | None,
    ) -> RunRecord:
        """Persist a one-shot or session turn result."""

        result_path = run_dir / RUN_RESULT_FILE
        events_path = run_dir / RUN_EVENTS_FILE if result.events else None
        write_json(
            result_path,
            json_model(result, exclude={"events", "raw"}),
        )
        if events_path is not None:
            write_events(events_path, result.events)
        session = result.session
        return RunRecord(
            id=run_id,
            kind="run",
            created_at=timestamp(),
            provider=str(result.provider),
            surface=str(result.surface) if result.surface is not None else None,
            status=str(result.status),
            cwd=path_or_none(cwd) or (session.cwd if session else None),
            agent=agent,
            collection=path_or_none(collection),
            provider_session_id=session.provider_session_id if session else None,
            run_dir=run_dir,
            result_path=result_path,
            events_path=events_path,
            event_count=len(result.events),
        )

    def record_workflow(
        self,
        run_id: str,
        run_dir: Path,
        result: WorkflowRun,
        *,
        agent: str | None,
        collection: str | Path | None,
        cwd: str | Path | None,
    ) -> RunRecord:
        """Persist a workflow result."""

        result_path = run_dir / RUN_RESULT_FILE
        events = workflow_events(result)
        events_path = run_dir / RUN_EVENTS_FILE if events else None
        write_json(
            result_path,
            json_model(result, exclude={"raw"}),
        )
        if events_path is not None:
            write_events(events_path, events)
        return RunRecord(
            id=run_id,
            kind="workflow",
            created_at=timestamp(),
            provider=str(result.provider),
            surface=str(result.surface) if result.surface is not None else None,
            status=str(result.status),
            cwd=path_or_none(cwd),
            agent=agent,
            collection=path_or_none(collection),
            provider_session_id=workflow_provider_session_id(result),
            run_dir=run_dir,
            result_path=result_path,
            events_path=events_path,
            event_count=len(events),
        )

    def load(self, id: str) -> RunRecord:
        """Load a stored run record by id."""

        path = self.runs_dir / id / RUN_RECORD_FILE
        return RunRecord.model_validate(json.loads(path.read_text()))

    def list(self) -> tuple[RunRecord, ...]:
        """List stored run records in newest-first order."""

        if not self.runs_dir.exists():
            return ()
        records = [
            self.load(path.parent.name)
            for path in self.runs_dir.glob(f"*/{RUN_RECORD_FILE}")
        ]
        return tuple(
            sorted(records, key=lambda record: record.created_at, reverse=True)
        )


def new_run_id() -> str:
    """Return a human-readable run id."""

    return f"run_{uuid4().hex[:12]}"


def timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).isoformat()


def path_or_none(value: str | Path | None) -> Path | None:
    """Normalize an optional path."""

    if value is None:
        return None
    return Path(value)


def workflow_events(result: WorkflowRun) -> tuple[Event, ...]:
    """Return normalized events nested in a workflow result."""

    events: list[Event] = []
    for step in result.steps:
        events.extend(step.run.events)
    return tuple(events)


def workflow_provider_session_id(result: WorkflowRun) -> str | None:
    """Return the first provider session id found in a workflow result."""

    for step in result.steps:
        if step.run.session and step.run.session.provider_session_id:
            return step.run.session.provider_session_id
    return None


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write pretty JSON."""

    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_events(path: Path, events: tuple[Event, ...]) -> None:
    """Write normalized events as JSON Lines."""

    lines = [
        json.dumps(json_model(event, exclude={"raw"}), sort_keys=True)
        for event in events
    ]
    path.write_text("\n".join(lines) + "\n")


def json_model(model: Any, *, exclude: set[str]) -> dict[str, Any]:
    """Return JSON-ready model data with volatile provider objects removed."""

    return model.model_dump(mode="json", exclude=exclude, exclude_none=True)
