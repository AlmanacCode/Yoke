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


def list_sessions(
    base_url: str,
    timeout_seconds: float,
    *,
    directory: str | None = None,
) -> tuple[JsonObject, ...]:
    params = {"directory": directory} if directory is not None else None
    response = httpx.get(f"{base_url}/session", params=params, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return ()
    return tuple(as_record(item) for item in payload if isinstance(item, dict))


def list_messages(
    base_url: str, session_id: str, timeout_seconds: float
) -> tuple[JsonObject, ...]:
    """List a session's stored messages via the documented history API.

    GET /session/:id/message (operationId session.messages), confirmed live
    (v1.17.15) to return every message in chronological order. No `limit` is
    passed here — OpenCode's own `limit` keeps the most *recent* N messages,
    which doesn't compose with offset-based pagination over the full
    (oldest-first) order; callers slice the full result locally instead.
    """

    response = httpx.get(
        f"{base_url}/session/{session_id}/message", timeout=timeout_seconds
    )
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


def update_session_permission(
    base_url: str,
    session_id: str,
    timeout_seconds: float,
    *,
    permission: tuple[JsonObject, ...],
) -> JsonObject:
    """Set a session's permission ruleset via PATCH /session/:id.

    Confirmed live (v1.17.15): `POST /session/:id/fork` does not inherit the
    parent's ruleset — a forked session starts with none at all (default
    allow) regardless of how restrictive the parent was. This PATCH endpoint
    is the only documented way to (re)apply one after the fact.
    """

    response = httpx.patch(
        f"{base_url}/session/{session_id}",
        json={"permission": list(permission)},
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
    *,
    system: str | None = None,
) -> JsonObject:
    body: JsonObject = {
        "model": {"providerID": provider_id, "modelID": model_id},
        "parts": [{"type": "text", "text": prompt}],
    }
    if system is not None:
        body["system"] = system
    response = httpx.post(
        f"{base_url}/session/{session_id}/message",
        params={"directory": cwd_directory},
        json=body,
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
