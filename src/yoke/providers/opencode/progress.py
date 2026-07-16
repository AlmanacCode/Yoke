"""Poll OpenCode's own SQLite db while a run is in flight.

Emits normalized Events for new parts across the root session and any
sub-agent sessions discovered along the way, and detects a tool call stuck
past a threshold. Runs on a background thread (see opencode_server.py, which
bridges this into the async ProviderAdapter surface via asyncio.to_thread)
because OpenCode's own SSE stream was found unreliable for this purpose in
the prior spike this module is ported from.

"Live" only covers terminal parts: a tool call still status: "running"
produces no TOOL_USE narration yet — it only feeds the stuck-call check.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from yoke.errors import YokeError
from yoke.models import Event
from yoke.providers.opencode.db import query_readonly_or_empty
from yoke.providers.opencode.fields import (
    JsonObject,
    as_record,
    number_field,
    string_field,
    stringify_json_value,
)
from yoke.providers.opencode.parts import is_task_spawn, map_opencode_part

Callback = Callable[[Event], None]

# Joins message to filter to assistant-authored parts only — part rows alone
# don't carry role, and a session's own part table includes the user's/
# prompt's echoed-back input parts too.
_PARTS_QUERY = """
SELECT part.id AS id, part.data AS part_data, message.data AS message_data
FROM part
JOIN message ON message.id = part.message_id
WHERE part.session_id = ?
ORDER BY part.time_created
"""

OPENCODE_POLL_INTERVAL_SECONDS = 2.0
OPENCODE_STUCK_TOOL_CALL_SECONDS = 240.0
# OpenCode's tool-execution layer has no internal timeout, so a glob/read/bash
# call can hang forever regardless of model — a confirmed upstream
# reliability gap, not fixable from this adapter, only detectable.
OPENCODE_STUCK_TOOL_CALL_ISSUE_URL = "github.com/anomalyco/opencode/issues/33541"


@dataclass
class OpencodeStuckToolCall:
    tool_name: str
    session_id: str
    elapsed_seconds: float
    tool_input: str | None = None


class OpencodeStuckToolCallError(YokeError):
    def __init__(self, info: OpencodeStuckToolCall):
        self.info = info
        super().__init__(
            f'OpenCode\'s "{info.tool_name}" tool call has been stuck for '
            f"{int(info.elapsed_seconds)}s+ with no response (session "
            f"{info.session_id}) — this is a known upstream OpenCode "
            f"reliability issue ({OPENCODE_STUCK_TOOL_CALL_ISSUE_URL}), not "
            "specific to this run."
        )


class OpencodeProgressWatchdog:
    def __init__(
        self,
        db_path: Path,
        root_session_id: str,
        on_event: Callback,
        poll_interval_seconds: float = OPENCODE_POLL_INTERVAL_SECONDS,
        stuck_after_seconds: float = OPENCODE_STUCK_TOOL_CALL_SECONDS,
        known_sessions: set[str] | None = None,
        seen_part_ids: set[str] | None = None,
    ) -> None:
        self.db_path = db_path
        self.on_event = on_event
        self.poll_interval_seconds = poll_interval_seconds
        self.stuck_after_seconds = stuck_after_seconds

        # Callers that span multiple turns on the same session (see
        # opencode_server.py's per-session _seen_part_ids/_known_sessions)
        # pass their own sets here so a later turn doesn't re-emit an
        # earlier turn's already-seen parts as if they were new.
        self._known_sessions: set[str] = (
            known_sessions if known_sessions is not None else set()
        )
        self._known_sessions.add(root_session_id)
        self._seen_part_ids: set[str] = (
            seen_part_ids if seen_part_ids is not None else set()
        )
        self.stuck_reason: OpencodeStuckToolCall | None = None

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self._poll_once()
            if self.stuck_reason is not None:
                return
            stop_event.wait(self.poll_interval_seconds)
        # One final pass: the DB is fully written by the time the caller sets
        # stop_event (only done after the blocking send returns), so this
        # picks up anything the last timed poll cycle missed.
        self._poll_once()

    def _poll_once(self) -> None:
        for session_id in tuple(self._known_sessions):
            self._poll_session(session_id)
            if self.stuck_reason is not None:
                return

    def _poll_session(self, session_id: str) -> None:
        rows = query_readonly_or_empty(self.db_path, _PARTS_QUERY, (session_id,))
        now_ms = int(time.time() * 1000)
        for row in rows:
            part_id = row["id"]
            if part_id in self._seen_part_ids:
                continue
            part = _parse_part(row["part_data"])
            if part is None:
                continue
            message = _parse_part(row["message_data"])
            if message is not None and string_field(message, "role") != "assistant":
                self._seen_part_ids.add(part_id)
                continue

            spawn = is_task_spawn(part)
            if spawn is not None:
                child_session_id, _ = spawn
                self._known_sessions.add(child_session_id)

            if string_field(part, "type") == "tool":
                state = as_record(part.get("state"))
                if string_field(state, "status") == "running":
                    self._check_stuck(session_id, part, state, now_ms)
                    if self.stuck_reason is not None:
                        return
                    continue  # not terminal yet — re-check next poll

            self._seen_part_ids.add(part_id)
            for event in map_opencode_part(part, session_id):
                self.on_event(event)

    def _check_stuck(
        self,
        session_id: str,
        part: JsonObject,
        state: JsonObject,
        now_ms: int,
    ) -> None:
        time_info = as_record(state.get("time"))
        start_ms = number_field(time_info, "start")
        if start_ms is None:
            return
        elapsed_seconds = (now_ms - start_ms) / 1000
        if elapsed_seconds >= self.stuck_after_seconds:
            self.stuck_reason = OpencodeStuckToolCall(
                tool_name=string_field(part, "tool") or "tool",
                session_id=session_id,
                elapsed_seconds=elapsed_seconds,
                tool_input=stringify_json_value(state.get("input")),
            )


def _parse_part(value: object) -> JsonObject | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
