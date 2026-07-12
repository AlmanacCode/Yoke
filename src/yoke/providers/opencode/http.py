"""Synchronous OpenCode HTTP client.

Endpoints per https://opencode.ai/docs/server/. One short-lived
`httpx.Client` per call keeps this module free of connection-lifetime state;
the caller owns the server process lifetime.
"""

from __future__ import annotations

import httpx

from yoke.providers.opencode.fields import JsonObject, as_record

OPENCODE_ALLOW_ALL_PERMISSION: tuple[JsonObject, ...] = (
    {"permission": "*", "pattern": "*", "action": "allow"},
)
OPENCODE_ASK_ALL_PERMISSION: tuple[JsonObject, ...] = (
    {"permission": "*", "pattern": "*", "action": "ask"},
)


def get_providers(base_url: str, timeout_seconds: float) -> tuple[JsonObject, ...]:
    response = httpx.get(f"{base_url}/config/providers", timeout=timeout_seconds)
    response.raise_for_status()
    payload = as_record(response.json())
    providers = payload.get("providers")
    if not isinstance(providers, list):
        return ()
    return tuple(as_record(item) for item in providers if isinstance(item, dict))


def create_session(
    base_url: str,
    cwd_directory: str,
    title: str,
    timeout_seconds: float,
    *,
    permission: tuple[JsonObject, ...] = OPENCODE_ALLOW_ALL_PERMISSION,
) -> JsonObject:
    body: JsonObject = {"title": title}
    if permission:
        body["permission"] = list(permission)
    response = httpx.post(
        f"{base_url}/session",
        params={"directory": cwd_directory},
        json=body,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return as_record(response.json())


def list_sessions(base_url: str, timeout_seconds: float) -> tuple[JsonObject, ...]:
    response = httpx.get(f"{base_url}/session", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return ()
    return tuple(as_record(item) for item in payload if isinstance(item, dict))


def read_session(base_url: str, session_id: str, timeout_seconds: float) -> JsonObject:
    response = httpx.get(f"{base_url}/session/{session_id}", timeout=timeout_seconds)
    response.raise_for_status()
    return as_record(response.json())


def rename_session(
    base_url: str,
    session_id: str,
    title: str,
    timeout_seconds: float,
) -> JsonObject:
    response = httpx.patch(
        f"{base_url}/session/{session_id}",
        json={"title": title},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return as_record(response.json())


def delete_session(base_url: str, session_id: str, timeout_seconds: float) -> None:
    response = httpx.delete(f"{base_url}/session/{session_id}", timeout=timeout_seconds)
    response.raise_for_status()


def fork_session(
    base_url: str,
    session_id: str,
    timeout_seconds: float,
    *,
    message_id: str | None = None,
) -> JsonObject:
    body: JsonObject = {"messageID": message_id} if message_id is not None else {}
    response = httpx.post(
        f"{base_url}/session/{session_id}/fork",
        json=body,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return as_record(response.json())


def abort_session(base_url: str, session_id: str, timeout_seconds: float) -> None:
    response = httpx.post(
        f"{base_url}/session/{session_id}/abort", timeout=timeout_seconds
    )
    response.raise_for_status()


def summarize_session(
    base_url: str,
    session_id: str,
    provider_id: str,
    model_id: str,
    timeout_seconds: float,
) -> None:
    response = httpx.post(
        f"{base_url}/session/{session_id}/summarize",
        json={"providerID": provider_id, "modelID": model_id},
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def post_message(
    base_url: str,
    session_id: str,
    cwd_directory: str,
    provider_id: str,
    model_id: str,
    prompt: str,
    timeout_seconds: float,
) -> JsonObject:
    response = httpx.post(
        f"{base_url}/session/{session_id}/message",
        params={"directory": cwd_directory},
        json={
            "model": {"providerID": provider_id, "modelID": model_id},
            "parts": [{"type": "text", "text": prompt}],
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return as_record(response.json())


def list_permissions(base_url: str, timeout_seconds: float) -> tuple[JsonObject, ...]:
    """List pending permission requests across all sessions.

    GET /permission (operationId permission.list) — confirmed live: a bash
    permission set to "ask" appeared here immediately and was still listed
    right up until it was answered via respond_permission(). This is the
    real, non-deprecated discovery mechanism; /session/:id/permissions/
    :permissionID (the endpoint this module used before) is marked
    deprecated in OpenCode's own OpenAPI doc.
    """

    response = httpx.get(f"{base_url}/permission", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return ()
    return tuple(as_record(item) for item in payload if isinstance(item, dict))


def respond_permission(
    base_url: str,
    permission_id: str,
    reply: str,
    timeout_seconds: float,
    *,
    message: str | None = None,
) -> None:
    """Answer a pending permission via POST /permission/:requestID/reply.

    `reply` is one of "once", "always", "reject" (OpenCode's own enum).
    """

    body: JsonObject = {"reply": reply}
    if message is not None:
        body["message"] = message
    response = httpx.post(
        f"{base_url}/permission/{permission_id}/reply",
        json=body,
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def set_auth(
    base_url: str,
    provider_id: str,
    api_key: str,
    timeout_seconds: float,
) -> None:
    response = httpx.put(
        f"{base_url}/auth/{provider_id}",
        json={"type": "api", "key": api_key},
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def list_agents(base_url: str, timeout_seconds: float) -> tuple[JsonObject, ...]:
    response = httpx.get(f"{base_url}/agent", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return ()
    return tuple(as_record(item) for item in payload if isinstance(item, dict))
