"""Structured-output helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jsonschema import SchemaError
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema.validators import validator_for
from pydantic import BaseModel, ValidationError

from yoke.models import Failure

OutputSchema = dict[str, Any] | type[BaseModel]


@dataclass(frozen=True)
class StructuredOutput:
    """Parsed structured output plus validation failure."""

    data: Any | None = None
    failure: Failure | None = None


def provider_schema(schema: OutputSchema | None) -> dict[str, Any] | None:
    """Return a closed JSON Schema accepted by Claude and Codex providers.

    Both live provider boundaries accept closed objects whose declared
    properties are explicitly required. Keeping this normalization shared
    prevents the same Pydantic model from changing shape between surfaces.
    Nested Pydantic models are normally emitted under ``$defs``, so strictness
    must be recursive rather than limited to the root object. Arbitrary mapping
    objects cannot satisfy that closed-object contract and are rejected rather
    than silently rewritten with different semantics.
    """

    if schema is None:
        return None
    value = schema if isinstance(schema, dict) else schema.model_json_schema()
    return strict_object_schemas(deepcopy(value))


def strict_object_schemas(value: Any) -> Any:
    """Make every JSON Schema object closed and explicitly required.

    Codex's structured-output boundary requires strict object schemas, including
    nested models stored under ``$defs`` and objects inside arrays.
    """

    if isinstance(value, list):
        return [strict_object_schemas(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {
        key: strict_object_schemas(item) for key, item in value.items()
    }
    if normalized.get("type") == "object":
        additional = normalized.get("additionalProperties")
        if additional not in (None, False):
            raise ValueError(
                "strict structured output cannot represent mapping objects; "
                "use a model with explicitly named fields"
            )
        normalized["additionalProperties"] = False
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties)
    return normalized


def parse_output_data(output: str | None, schema: OutputSchema | None) -> Any | None:
    """Parse provider text as JSON only when structured output was requested."""

    return parse_output(output, schema).data


def parse_output(output: str | None, schema: OutputSchema | None) -> StructuredOutput:
    """Parse and validate provider text when structured output was requested."""

    if schema is None or output is None:
        return StructuredOutput()
    text = output.strip()
    if not text:
        return StructuredOutput()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return StructuredOutput(
            failure=Failure(
                message="provider returned invalid JSON for structured output",
                code="invalid_structured_json",
                raw=output,
            )
        )
    if isinstance(schema, dict):
        try:
            validator = validator_for(schema)
            validator.check_schema(schema)
            validator(schema).validate(data)
        except (SchemaError, JsonSchemaValidationError) as error:
            return StructuredOutput(
                failure=Failure(
                    message="provider structured output did not match schema",
                    code="invalid_structured_output",
                    raw=str(error),
                )
            )
        return StructuredOutput(data=data)
    try:
        return StructuredOutput(data=schema.model_validate(data))
    except ValidationError as error:
        return StructuredOutput(
            failure=Failure(
                message="provider structured output did not match schema",
                code="invalid_structured_output",
                raw=str(error),
            )
        )
