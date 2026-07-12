"""Loose JSON field helpers shared by providers with no typed SDK payloads.

Codex app-server and OpenCode both talk to their provider over JSON (JSON-RPC
and HTTP respectively) rather than a typed Python SDK, so both need the same
small set of "read this field defensively" helpers. Kept here once so a fix
to one provider's field parsing doesn't quietly diverge from the other's.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard

from pydantic import JsonValue

JsonObject = dict[str, JsonValue]


def as_record(value: JsonValue | None) -> JsonObject:
    if is_record(value):
        return value
    return {}


def is_record(value: JsonValue | None) -> TypeGuard[JsonObject]:
    return isinstance(value, dict)


def string_field(record: Mapping[str, JsonValue], field: str) -> str | None:
    value = record.get(field)
    if isinstance(value, str) and value != "":
        return value
    return None


def number_field(record: Mapping[str, JsonValue], field: str) -> int | None:
    value = record.get(field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
