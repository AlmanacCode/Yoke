"""Replay contracts for Yoke-owned workflow orchestration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from yoke.models import Run


@runtime_checkable
class WorkflowReplay(Protocol):
    """Store completed workflow agent calls for later replay."""

    def get(self, run_id: str, key: str) -> Run | None:
        """Return a cached run for this flow run id and call key."""

    def put(self, run_id: str, key: str, run: Run) -> None:
        """Store a run for later resume/replay."""
