from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from yoke.models import EventKind
from yoke.providers.opencode.progress import (
    OpencodeProgressWatchdog,
    OpencodeStuckToolCall,
)


def _make_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT, "
        "time_created INTEGER)"
    )
    connection.execute(
        "CREATE TABLE part (id TEXT PRIMARY KEY, session_id TEXT, message_id TEXT, "
        "data TEXT, time_created INTEGER)"
    )
    connection.commit()
    connection.close()


def _insert_part(
    path: Path,
    *,
    part_id: str,
    session_id: str,
    message_id: str,
    role: str,
    part: dict,
    seq: int,
) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT OR IGNORE INTO message (id, session_id, data, time_created) "
        "VALUES (?, ?, ?, ?)",
        (message_id, session_id, json.dumps({"role": role}), seq),
    )
    connection.execute(
        "INSERT INTO part (id, session_id, message_id, data, time_created) "
        "VALUES (?, ?, ?, ?, ?)",
        (part_id, session_id, message_id, json.dumps(part), seq),
    )
    connection.commit()
    connection.close()


def test_watchdog_emits_events_for_assistant_parts(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_part(
        db_path,
        part_id="p1",
        session_id="root",
        message_id="m1",
        role="assistant",
        part={"type": "text", "text": "hello"},
        seq=1,
    )

    events = []
    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=events.append,
        poll_interval_seconds=0.01,
        stuck_after_seconds=999,
    )
    watchdog._poll_once()

    assert len(events) == 1
    assert events[0].kind == EventKind.TEXT
    assert events[0].message == "hello"


def test_watchdog_ignores_user_authored_parts(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_part(
        db_path,
        part_id="p1",
        session_id="root",
        message_id="m1",
        role="user",
        part={"type": "text", "text": "prompt echo"},
        seq=1,
    )

    events = []
    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=events.append,
        poll_interval_seconds=0.01,
    )
    watchdog._poll_once()

    assert events == []


def test_watchdog_does_not_reemit_seen_parts(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_part(
        db_path,
        part_id="p1",
        session_id="root",
        message_id="m1",
        role="assistant",
        part={"type": "text", "text": "hello"},
        seq=1,
    )

    events = []
    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=events.append,
        poll_interval_seconds=0.01,
    )
    watchdog._poll_once()
    watchdog._poll_once()

    assert len(events) == 1


def test_watchdog_does_not_reemit_prior_turn_parts_across_sessions(
    tmp_path: Path,
) -> None:
    # Regression: a live multi-turn smoke test found that a fresh watchdog
    # per send() re-polled the whole session and re-emitted an earlier
    # turn's already-seen parts as if they were new. Sharing known_sessions/
    # seen_part_ids across watchdog instances (as opencode_server.py's
    # per-session _OpencodeSession does) must prevent that.
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_part(
        db_path,
        part_id="turn1-part",
        session_id="root",
        message_id="m1",
        role="assistant",
        part={"type": "text", "text": "turn one output"},
        seq=1,
    )

    known_sessions: set[str] = set()
    seen_part_ids: set[str] = set()
    first_turn_events = []
    first_watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=first_turn_events.append,
        poll_interval_seconds=0.01,
        known_sessions=known_sessions,
        seen_part_ids=seen_part_ids,
    )
    first_watchdog._poll_once()
    assert len(first_turn_events) == 1

    _insert_part(
        db_path,
        part_id="turn2-part",
        session_id="root",
        message_id="m2",
        role="assistant",
        part={"type": "text", "text": "turn two output"},
        seq=2,
    )

    second_turn_events = []
    second_watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=second_turn_events.append,
        poll_interval_seconds=0.01,
        known_sessions=known_sessions,
        seen_part_ids=seen_part_ids,
    )
    second_watchdog._poll_once()

    assert len(second_turn_events) == 1
    assert second_turn_events[0].message == "turn two output"


def test_watchdog_discovers_child_session_from_task_spawn(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    _insert_part(
        db_path,
        part_id="p1",
        session_id="root",
        message_id="m1",
        role="assistant",
        part={
            "type": "tool",
            "tool": "task",
            "state": {
                "status": "completed",
                "input": {"prompt": "help"},
                "metadata": {"sessionId": "child-1"},
            },
        },
        seq=1,
    )
    _insert_part(
        db_path,
        part_id="p2",
        session_id="child-1",
        message_id="m2",
        role="assistant",
        part={"type": "text", "text": "child output"},
        seq=2,
    )

    events = []
    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=events.append,
        poll_interval_seconds=0.01,
    )
    watchdog._poll_once()
    # Child session was discovered mid-poll; a second pass picks up its parts.
    watchdog._poll_once()

    assert "child-1" in watchdog._known_sessions
    child_texts = [e.message for e in events if e.kind == EventKind.TEXT]
    assert "child output" in child_texts


def test_watchdog_detects_stuck_tool_call(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)
    stale_start_ms = int(time.time() * 1000) - 1_000_000
    _insert_part(
        db_path,
        part_id="p1",
        session_id="root",
        message_id="m1",
        role="assistant",
        part={
            "type": "tool",
            "tool": "bash",
            "state": {
                "status": "running",
                "time": {"start": stale_start_ms},
                "input": {"command": "sleep 999"},
            },
        },
        seq=1,
    )

    events = []
    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=events.append,
        poll_interval_seconds=0.01,
        stuck_after_seconds=1,
    )
    watchdog._poll_once()

    assert isinstance(watchdog.stuck_reason, OpencodeStuckToolCall)
    assert watchdog.stuck_reason.tool_name == "bash"
    assert events == []


def test_watchdog_run_stops_on_stop_event(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _make_db(db_path)

    watchdog = OpencodeProgressWatchdog(
        db_path=db_path,
        root_session_id="root",
        on_event=lambda event: None,
        poll_interval_seconds=0.01,
    )
    stop_event = threading.Event()
    thread = threading.Thread(target=watchdog.run, args=(stop_event,))
    thread.start()
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
