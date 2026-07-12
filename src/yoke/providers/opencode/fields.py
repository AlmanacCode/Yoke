"""Loose JSON field helpers for OpenCode HTTP/DB payloads."""

from __future__ import annotations

import json
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


def stringify_json_value(value: JsonValue | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
