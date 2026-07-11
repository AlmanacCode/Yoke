# 0160 - Workflow channel selection fix

## Context

Yoke treats `channel` as a first-class provider exposure axis. A caller can ask for a provider through a specific exposure path, such as Codex app server instead of Codex CLI, because the same provider does not expose the same features through every surface.

## Bug

`Harness.workflow(...)` had a call-shape mistake while threading channel-aware workflow feature checks into `require(...)`. The workflow itself was passed twice into `workflow_features(...)`.

That made workflow execution fragile exactly where the SDK needs to be most precise: selecting the right surface for a requested channel before running a multi-step workflow.

## Fix

`Harness.workflow(...)` now passes the workflow, workflow options, agent, and provider once to `workflow_features(...)`, then forwards `WorkflowOptions.channel` into `Harness.require(...)`.

A focused test registers a fake Codex app-server adapter and runs a workflow through:

```python
await harness.workflow(
    workflow,
    "hello",
    WorkflowOptions(channel=Channel.APP_SERVER),
)
```

The test asserts the workflow ran on `codex_app_server`, not a generic Codex surface.

## Design note

This reinforces the current Yoke model:

- `provider` says which harness family the caller wants.
- `channel` says how the caller wants to reach that provider.
- `surface` is the concrete adapter selected by capability, readiness, and channel constraints.

That distinction matters for Codex because the app server appears to expose richer live/session behavior than the CLI path. It also matters for Claude because CLI, SDK, and future workflow APIs may not stay feature-equivalent.

## Verification

- `PYTHONPATH=src uv run pytest tests/test_workflows.py` -> 9 passed.
- `uv run ruff check src/yoke/models.py tests/test_workflows.py` -> passed.
