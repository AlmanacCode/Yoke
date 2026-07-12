"""Loose JSON field helpers for Codex app-server payloads."""

from __future__ import annotations

import json
from typing import TypeVar

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
    "compact_json",
    "first_present",
    "is_record",
    "number_field",
    "string_field",
]

T = TypeVar("T")


def compact_json(value: JsonValue) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def first_present(*values: T | None) -> T | None:
    for value in values:
        if value is not None:
            return value
    return None
