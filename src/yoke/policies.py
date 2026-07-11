"""Reusable provider request policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from yoke.models import Event, EventKind, RequestKind, Response, ToolKind, YokeModel


class RequestPolicy(YokeModel):
    """Small provider-neutral policy for Yoke request payloads."""

    response: Response = Response.deny()
    request_kinds: tuple[RequestKind | str, ...] = ()
    tool_kinds: tuple[ToolKind | str, ...] = ()
    methods: tuple[str, ...] = ()

    @classmethod
    def allow_all(cls) -> RequestPolicy:
        """Allow every request that reaches this policy."""

        return cls(response=Response.allow())

    @classmethod
    def deny_all(cls, message: str = "Denied by Yoke.") -> RequestPolicy:
        """Deny every request that reaches this policy."""

        return cls(response=Response.deny(message))

    @classmethod
    def allow_tools(cls, *kinds: ToolKind | str) -> RequestPolicy:
        """Allow only requests for specific normalized tool kinds."""

        return cls(response=Response.allow(), tool_kinds=kinds)

    @classmethod
    def deny_tools(
        cls,
        *kinds: ToolKind | str,
        message: str = "Denied by Yoke.",
    ) -> RequestPolicy:
        """Deny only requests for specific normalized tool kinds."""

        return cls(response=Response.deny(message), tool_kinds=kinds)

    def __call__(
        self,
        event: Event,
        default: Response | None = None,
    ) -> Response | None:
        """Return a response override, or the caller's default response."""

        if event.request is None:
            return default
        if self.request_kinds and event.request.kind not in self.request_kinds:
            return default
        if self.methods and event.request.method not in self.methods:
            return default
        if self.tool_kinds and not self.matches_tool_kind(event):
            return default
        return self.response

    def matches_tool_kind(self, event: Event) -> bool:
        """Return whether the event's normalized tool kind is in scope."""

        if event.tool is None:
            return False
        return event.tool.kind in self.tool_kinds


class CodexApprovalDecision(StrEnum):
    """Documented Codex app-server approval decisions."""

    ACCEPT = "accept"
    ACCEPT_FOR_SESSION = "acceptForSession"
    DECLINE = "decline"
    CANCEL = "cancel"


class CodexRequestPolicy(YokeModel):
    """Conservative Codex app-server request policy.

    This helper is intentionally scoped to Codex app-server request events. It
    does not pretend that Codex CLI, Codex SDK, and app-server expose identical
    approval surfaces.
    """

    decision: CodexApprovalDecision | str = CodexApprovalDecision.DECLINE
    tool_kinds: tuple[ToolKind | str, ...] = ()
    methods: tuple[str, ...] = (
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
    )

    @classmethod
    def decline_all(cls) -> CodexRequestPolicy:
        """Decline modern Codex app-server approval requests."""

        return cls(decision=CodexApprovalDecision.DECLINE)

    @classmethod
    def accept_all(cls) -> CodexRequestPolicy:
        """Accept modern Codex app-server approval requests."""

        return cls(decision=CodexApprovalDecision.ACCEPT)

    @classmethod
    def accept_for_session(cls) -> CodexRequestPolicy:
        """Accept modern Codex app-server approval requests for the session."""

        return cls(decision=CodexApprovalDecision.ACCEPT_FOR_SESSION)

    @classmethod
    def accept_tools(cls, *kinds: ToolKind | str) -> CodexRequestPolicy:
        """Accept modern approval requests only for specific tool kinds."""

        return cls(decision=CodexApprovalDecision.ACCEPT, tool_kinds=kinds)

    def __call__(self, event: Event, default: Any) -> dict[str, str] | Any | None:
        """Return a JSON-RPC result override, or let Yoke use the default."""

        if event.kind is not EventKind.APPROVAL_REQUEST:
            return None
        if event.tool_name not in self.methods:
            return default
        if self.tool_kinds and not self.matches_tool_kind(event):
            return default
        return {"decision": str(self.decision)}

    def matches_tool_kind(self, event: Event) -> bool:
        """Return whether the event's normalized tool kind is allowed."""

        if event.tool is None:
            return False
        return event.tool.kind in self.tool_kinds
