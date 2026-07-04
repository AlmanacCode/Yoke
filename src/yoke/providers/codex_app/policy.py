"""Permission translation for Codex app-server."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import JsonValue

from yoke.models import Access, Approval

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]


def sandbox_mode(permissions: Any) -> SandboxMode:
    access = permissions.access
    if access is Access.FULL or str(access).endswith("full"):
        return "danger-full-access"
    if access is Access.WRITE or str(access).endswith("write"):
        return "workspace-write"
    return "read-only"


def sandbox_policy(cwd: Path, mode: SandboxMode) -> dict[str, JsonValue]:
    if mode == "danger-full-access":
        return {"type": "dangerFullAccess"}
    if mode == "read-only":
        return {"type": "readOnly"}
    return {
        "type": "workspaceWrite",
        "writableRoots": [str(cwd)],
        "networkAccess": False,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def approval_policy(permissions: Any) -> str:
    approval = permissions.approval
    if approval is Approval.AUTO or str(approval).endswith("auto"):
        return "on-failure"
    if approval is Approval.ASK or str(approval).endswith("ask"):
        return "on-request"
    return "never"
