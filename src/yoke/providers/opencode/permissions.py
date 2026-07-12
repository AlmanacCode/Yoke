"""Poll OpenCode's pending-permission list and resolve it through a policy.

`GET /permission` is a real, non-deprecated, polling-discoverable endpoint —
confirmed live in a 2026-07-12 spike: a session created with a bash
permission set to "ask" produced a pending entry here immediately, and the
in-flight `POST /session/:id/message` call (blocked waiting on that specific
permission) completed as soon as it was answered via
`POST /permission/:id/reply`. That disproves this adapter's earlier
assumption that a pending permission is "only learnable via SSE" — it fits
the same poll-not-SSE architecture as `OpencodeProgressWatchdog`
(progress.py), not a generated plugin or a local HTTP callback listener.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from yoke.models import (
    Event,
    EventKind,
    Request,
    RequestKind,
    Response,
    Tool,
    ToolStatus,
)
from yoke.providers.opencode import http
from yoke.providers.opencode.fields import JsonObject, string_field
from yoke.providers.opencode.parts import infer_opencode_tool_kind

Callback = Callable[[Event], None]

OPENCODE_PERMISSION_POLL_INTERVAL_SECONDS = 1.0
OPENCODE_PERMISSION_REQUEST_TIMEOUT_SECONDS = 10.0


class OpencodePermissionWatchdog:
    """Poll pending permissions for one session and resolve them via a handler."""

    def __init__(
        self,
        base_url: str,
        session_id: str,
        on_event: Callback,
        request_handler: object | None,
        poll_interval_seconds: float = OPENCODE_PERMISSION_POLL_INTERVAL_SECONDS,
        timeout_seconds: float = OPENCODE_PERMISSION_REQUEST_TIMEOUT_SECONDS,
        seen_permission_ids: set[str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.session_id = session_id
        self.on_event = on_event
        self.request_handler = request_handler
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self._seen: set[str] = (
            seen_permission_ids if seen_permission_ids is not None else set()
        )

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self._poll_once()
            stop_event.wait(self.poll_interval_seconds)
        # One final pass: a permission asked right before the sender thread
        # returned could otherwise go unanswered and unreported.
        self._poll_once()

    def _poll_once(self) -> None:
        try:
            pending = http.list_permissions(self.base_url, self.timeout_seconds)
        except Exception:  # noqa: BLE001 - transient poll errors retried next tick
            return
        for record in pending:
            permission_id = string_field(record, "id")
            if permission_id is None or permission_id in self._seen:
                continue
            if string_field(record, "sessionID") != self.session_id:
                continue
            self._seen.add(permission_id)
            self._resolve(record, permission_id)

    def _resolve(self, record: JsonObject, permission_id: str) -> None:
        event = permission_event(record, permission_id)
        response = policy_response(event, self.request_handler)
        reply = "once" if response.decision == "allow" else "reject"
        try:
            http.respond_permission(
                self.base_url,
                permission_id,
                reply,
                self.timeout_seconds,
                message=response.message,
            )
        except Exception:  # noqa: BLE001 - reply failures surface on the model's turn
            return
        self.on_event(
            event.model_copy(
                update={"kind": EventKind.REQUEST_RESOLVED, "response": response}
            )
        )


def permission_event(record: JsonObject, permission_id: str) -> Event:
    """Build the provider-neutral event for one pending OpenCode permission."""

    permission_kind = string_field(record, "permission") or "permission"
    metadata = record.get("metadata")
    command = (
        string_field(metadata, "command") if isinstance(metadata, dict) else None
    )
    tool = Tool(
        kind=infer_opencode_tool_kind(permission_kind),
        title=permission_kind,
        command=command,
        status=ToolStatus.STARTED,
    )
    message = f"OpenCode requested {permission_kind} permission"
    # Fail closed, matching RequestPolicy's own default (policies.py): a
    # permission this adapter can't resolve is denied, not silently left
    # pending until the caller's timeout.
    default = Response.deny(f"Denied by Yoke: no permission policy for {message!r}.")
    return Event(
        kind=EventKind.APPROVAL_REQUEST,
        message=message,
        tool_id=permission_id,
        tool_name=permission_kind,
        tool=tool,
        request=Request(
            kind=RequestKind.PERMISSION,
            id=permission_id,
            method=permission_kind,
            message=message,
            tool=tool,
            input=record,
            default=default,
            raw=record,
        ),
        response=default,
        source_thread_id=string_field(record, "sessionID"),
        raw=record,
    )


def policy_response(event: Event, request_handler: object | None) -> Response:
    """Return the handler's decision, or the event's default if none applies."""

    default = event.response or Response.deny()
    if request_handler is None or not callable(request_handler):
        return default
    response = request_handler(event, default)
    return response if isinstance(response, Response) else default
