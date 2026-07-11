# Workflow step results are traces

Yoke portable workflows now preserve step execution metadata on each
`StepResult`.

Each step result records:

- `mode`
- `provider`
- `surface`
- `depends_on`
- `prompt`
- `run`

The runner already knew these values while scheduling. Keeping them on
`StepResult` makes workflow output easier to render in app UIs, logs, and test
assertions without inventing a second workflow-log file.

This also matches the provider split:

- Claude native workflows are background script runs with task/run IDs and
  transcript directories.
- Yoke portable workflows are local DAG orchestration over provider turns.

Trace metadata belongs in the portable `StepResult`; provider-native adapters
can still return `WorkflowRun(mode="provider_native")` with provider-specific
data.

Sources:

- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/agent-sdk/typescript

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_workflows.py tests/test_capabilities.py
uv run ruff check src/yoke/models.py src/yoke/workflows.py tests/test_workflows.py
```

Observed:

```text
92 passed
All checks passed!
```
