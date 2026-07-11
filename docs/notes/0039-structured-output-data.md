# Structured output data

Date: 2026-07-04

Yoke now separates human-readable output from structured output:

```python
result.output  # text
result.data    # parsed structured value
```

`Run.data` is the provider-neutral home for parsed structured output. `WorkflowRun.data` mirrors the final step's `Run.data`.

Callers can pass either a JSON Schema dict or a Pydantic model class:

```python
class Summary(BaseModel):
    summary: str
    changed: bool


result = await harness.run(
    "Return a summary object.",
    RunOptions(output_schema=Summary),
)

result.data.summary
```

Provider behavior:

- Claude Agent SDK native `structured_output` maps directly to `Run.data`.
- Pydantic model classes are converted to JSON Schema before provider calls.
- Codex CLI and Codex app-server attempt JSON parsing only when `output_schema` was requested.
- When the requested schema is a Pydantic model class, parsed JSON is validated into that model.
- Invalid JSON text produces `Run(status=RunStatus.FAILED, failure=Failure(code="invalid_structured_json"))`.
- JSON that fails Pydantic validation produces `Run(status=RunStatus.FAILED, failure=Failure(code="invalid_structured_output"))`.

This keeps Yoke useful for embedding apps. CodeAlmanac can map `Run.data` to operation reports without scraping final assistant prose, while still preserving `Run.output` for logs and human summaries.
