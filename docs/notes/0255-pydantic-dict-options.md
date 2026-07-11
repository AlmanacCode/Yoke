# 0255 - Pydantic dict options are real options

Date: 2026-07-04

## Change

`Harness.run(...)`, `Harness.stream(...)`, `Harness.start(...)`, and
`Harness.workflow(...)` now validate plain dictionaries into the matching
Pydantic option models instead of silently replacing them with defaults.

Examples that now work:

```python
await harness.run(
    "Ship the change.",
    {"goal": {"objective": "Finish safely."}},
)

await harness.workflow(
    workflow,
    "Audit the repo.",
    {"native": True},
)
```

## Why

Yoke is intended to be Pydantic-native and folder-native. Folder YAML and app
request bodies naturally arrive as dictionaries. Before this change, dict
options were ignored unless the caller manually constructed `RunOptions`,
`SessionOptions`, or `WorkflowOptions`.

That was a correctness bug because `native=True`, `goal`, `output_schema`,
`permissions`, and provider options could vanish at the public API boundary.

## Verification

Focused tests:

```bash
PYTHONPATH=src uv run pytest \
  tests/test_workflows.py \
  tests/test_capabilities.py \
  tests/test_public_api.py
```

Result:

```text
113 passed
```

Ruff:

```bash
PYTHONPATH=src uv run ruff check src/yoke/models.py tests/test_workflows.py
```

Result:

```text
All checks passed!
```
