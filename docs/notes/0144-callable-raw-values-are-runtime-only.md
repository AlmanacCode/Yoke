# Callable raw values are runtime-only

Date: 2026-07-04

Yoke now reports callables anywhere inside option trees as runtime-only values.

The `raw` fields are still useful. They let callers pass provider fields before Yoke has typed them. Serializable raw data belongs in the folder model when it is authored intent. A Python callable inside `raw` is different: it is executable SDK code, not data.

Example report path:

```text
provider.codex.raw.callback
```

When such a callable appears inside a workflow step run option, `Agent.save(...)` now fails before writing files:

```text
workflows.review.steps.review.run.provider.codex.raw.callback
```

This keeps the folder contract honest. `raw` is not a back door around the SDK/folder boundary. It is a typed escape hatch for provider data that Yoke has not modeled yet. Live callbacks still belong in SDK code and require `allow_runtime_only=True` if a caller intentionally wants a lossy folder snapshot.

Design implication: future provider escape hatches should be audited by value kind, not just by field name. Dicts, strings, numbers, booleans, lists, and nested pydantic models can be serialized. Callables, client objects, process handles, and live transports should be reported as runtime-only.
