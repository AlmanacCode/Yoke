# Agent workflows drive surface planning

2026-07-04

Yoke planning now includes workflows declared on the `Agent` itself.

Earlier planning included features implied by run options and agent fields such as `goal`, `skills`, and `subagents`, but `agent.workflows` did not contribute to `Agent.features()`. That made folder-declared workflows less visible to `Harness.plan()` than other agent-shape features.

`Agent.features()` now returns `Feature.WORKFLOW` when `agent.workflows` is non-empty. This keeps folder-first agents honest: a folder with workflows is not just a plain one-shot agent.

This does not imply `Feature.NATIVE_WORKFLOW`. Native workflow support is still required when a specific native/script workflow is executed or requested through `WorkflowOptions(native=True)`. A workflow declaration on an agent means the agent has workflow recipes; it does not by itself mean every run requires a provider-native workflow runtime.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_workflows.py tests/test_folders.py`
- `PYTHONPATH=src uv run ruff check src/yoke/models.py tests/test_capabilities.py`
