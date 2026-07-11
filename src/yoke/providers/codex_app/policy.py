"""Permission translation for Codex app-server."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import JsonValue

from yoke.models import Access, Approval
from yoke.options import CodexOptions

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]


def sandbox_mode(
    permissions: Any,
    options: CodexOptions | dict[str, Any] | None = None,
) -> SandboxMode:
    native = codex_option(options, "sandbox")
    if native is not None:
        return str(native)  # type: ignore[return-value]
    access = permissions.access
    if access is Access.FULL or str(access).endswith("full"):
        return "danger-full-access"
    if access is Access.WRITE or str(access).endswith("write"):
        return "workspace-write"
    return "read-only"


def sandbox_policy(
    cwd: Path,
    mode: SandboxMode,
    *,
    network: bool = False,
    writable_roots: tuple[str, ...] = (),
) -> dict[str, JsonValue]:
    if mode == "danger-full-access":
        return {"type": "dangerFullAccess"}
    if mode == "read-only":
        return {"type": "readOnly"}
    return {
        "type": "workspaceWrite",
        "writableRoots": [*writable_roots] or [str(cwd)],
        "networkAccess": network,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def approval_policy(
    permissions: Any,
    options: CodexOptions | dict[str, Any] | None = None,
) -> str:
    native = codex_option(options, "approval")
    if native is not None:
        return str(native)
    approval = permissions.approval
    if approval is Approval.AUTO or str(approval).endswith("auto"):
        return "on-failure"
    if approval is Approval.ASK or str(approval).endswith("ask"):
        return "on-request"
    return "never"


def network_access(
    permissions: Any,
    options: CodexOptions | dict[str, Any] | None = None,
) -> bool:
    native = codex_option(options, "network")
    if native is not None:
        return bool(native)
    return bool(getattr(permissions, "network", False))


def writable_roots(
    options: CodexOptions | dict[str, Any] | None = None,
) -> tuple[str, ...]:
    native = codex_option(options, "writable_roots")
    if native is None:
        return ()
    if isinstance(native, str):
        return (native,)
    if isinstance(native, tuple | list):
        return tuple(str(item) for item in native if item is not None)
    return ()


def codex_option(
    options: CodexOptions | dict[str, Any] | None,
    field: str,
) -> Any | None:
    if options is None:
        return None
    if isinstance(options, CodexOptions):
        value = getattr(options, field)
        if value is not None and value != ():
            return value
        raw_value = options.raw.get(field)
        if raw_value is not None:
            return raw_value
        camel = {
            "approval": "approvalPolicy",
            "approvals_reviewer": "approvalsReviewer",
            "permissions": "permissionProfile",
            "network": "networkAccess",
            "writable_roots": "writableRoots",
            "runtime_workspace_roots": "runtimeWorkspaceRoots",
            "selected_capability_roots": "selectedCapabilityRoots",
            "allow_provider_model_fallback": "allowProviderModelFallback",
            "service_tier": "serviceTier",
            "client_user_message_id": "clientUserMessageId",
        }.get(field)
        if camel is not None:
            value = options.raw.get(camel)
            if value is not None:
                return value
        if field == "permissions":
            return options.raw.get("permission_profile")
        return None
    value = options.get(field)
    if value is not None:
        return value
    camel = {
        "approval": "approvalPolicy",
        "approvals_reviewer": "approvalsReviewer",
        "permissions": "permissionProfile",
        "network": "networkAccess",
        "writable_roots": "writableRoots",
        "runtime_workspace_roots": "runtimeWorkspaceRoots",
        "selected_capability_roots": "selectedCapabilityRoots",
        "allow_provider_model_fallback": "allowProviderModelFallback",
        "service_tier": "serviceTier",
        "client_user_message_id": "clientUserMessageId",
    }.get(field)
    if camel is not None:
        value = options.get(camel)
        if value is not None:
            return value
    if field == "permissions":
        return options.get("permission_profile")
    return None
