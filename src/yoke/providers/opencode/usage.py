"""Parse OpenCode's token usage payload into normalized Yoke usage."""

from __future__ import annotations

from pydantic import JsonValue

from yoke.models import Usage
from yoke.providers.opencode.fields import as_record, number_field


def parse_opencode_usage(value: JsonValue | None) -> Usage | None:
    obj = as_record(value)
    if len(obj) == 0:
        return None
    cache = as_record(obj.get("cache"))
    return Usage(
        input_tokens=number_field(obj, "input"),
        cached_input_tokens=number_field(cache, "read"),
        output_tokens=number_field(obj, "output"),
        reasoning_output_tokens=number_field(obj, "reasoning"),
        total_tokens=number_field(obj, "total"),
    )
