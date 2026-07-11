# 0242 - Native workflow boundary

Date: 2026-07-04

Yoke now has one shared error boundary for provider-native workflow requests that reach a surface without a real native workflow adapter.

## What changed

- `src/yoke/workflows.py` exposes `native_workflow_unsupported(...)` and `native_workflow_body(...)`.
- The runtime native path uses the shared helper when a selected adapter has no `workflow(...)` method.
- Claude Python SDK, Codex CLI, Codex Python SDK, and Codex app-server adapters now all use the same wording when they reject provider-native workflow execution.
- The error includes provider, surface, workflow name, native input shape, and a concrete fallback: use portable step workflows or `Workflow.run(...)` on the surface.

## Design decision

Yoke should not pretend that native workflows are available everywhere. Portable workflows are Yoke-owned and can run across providers. Provider-native workflows need a provider surface that actually exposes a native workflow DSL or execution hook.

Claude Python SDK is still the runnable Claude surface in Yoke. Claude's documented native Workflow tool belongs to the TypeScript SDK surface, so the Python adapter rejects provider-native workflow execution with an explicit reason.

Codex app-server has rich thread, event, subagent, goal-loop, and request-control APIs, but Yoke has not found a documented provider-native workflow DSL for that surface. Codex native workflow support should stay unsupported until there is a real provider hook or Yoke intentionally builds a Codex-native translation layer.

## Verified

Focused workflow/capability/readiness tests passed:

```bash
PYTHONPATH=src uv run pytest tests/test_workflows.py tests/test_capabilities.py::test_native_workflow_planning_selects_tracked_provider_native_surface tests/test_capabilities.py::test_native_workflow_planning_rejects_runnable_python_surface tests/test_readiness.py::test_status_workflow_report_names_portable_workflow_surfaces tests/test_readiness.py::test_status_workflow_report_names_provider_native_workflow_surfaces
```

Result: 22 passed.

Focused ruff passed:

```bash
PYTHONPATH=src uv run ruff check src/yoke/workflows.py src/yoke/providers/claude.py src/yoke/providers/codex.py src/yoke/providers/codex_sdk.py src/yoke/providers/codex_app_server.py tests/test_workflows.py
```

Result: all checks passed.
