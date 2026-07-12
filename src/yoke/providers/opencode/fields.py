"""Loose JSON field helpers for OpenCode HTTP/DB payloads."""

from __future__ import annotations

import json

from pydantic import JsonValue

from yoke.providers._fields import (
    JsonObject,
    as_record,
    is_record,
    number_field,
    string_field,
)

__all__ = [
    "JsonObject",
    "as_record",
    "is_record",
    "number_field",
    "string_field",
    "stringify_json_value",
]


def stringify_json_value(value: JsonValue | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
