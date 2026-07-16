"""Classify OpenCode run failures into normalized Yoke failures."""

from __future__ import annotations

from yoke.models import Failure
from yoke.providers.opencode.progress import OPENCODE_STUCK_TOOL_CALL_ISSUE_URL


def classify_opencode_failure(message: str, code: str | None = None) -> Failure:
    if "not found on PATH" in message:
        return Failure(
            code="opencode.not_installed",
            message="OpenCode was not found on PATH.",
            fix=(
                "Install OpenCode or update PATH so the `opencode` command "
                "is available."
            ),
            raw=message,
        )
    if (
        "did not report a listening port" in message
        or "exited before it started listening" in message
    ):
        return Failure(
            code="opencode.server_start_failed",
            message=message,
            fix="Run `opencode serve` directly to check for a startup error.",
            raw=message,
        )
    if "tool call has been stuck" in message:
        return Failure(
            code="opencode.stuck_tool_call",
            message=message,
            fix=(
                "This is a known upstream OpenCode reliability issue "
                f"({OPENCODE_STUCK_TOOL_CALL_ISSUE_URL}), not specific to this "
                "run. Retrying often succeeds; a different model may avoid the "
                "tool call shape that triggers it."
            ),
            raw=message,
        )
    if "timed out" in message:
        return Failure(code="opencode.timeout", message=message, raw=message)
    return Failure(code=code or "opencode.request_failed", message=message, raw=message)
