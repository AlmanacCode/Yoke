# Workflow runs report their execution surface

Date: 2026-07-04

`WorkflowRun` now records how the workflow execution happened.

The initial mode is `yoke_portable`, which means Yoke ran the workflow as a small DAG over provider turns. The result also records the selected provider and surface, such as `claude/fake` in tests or `codex/codex_app_server` for an app-server channel selection.

Each `StepResult` records the Yoke agent name used for that step. This matters because a portable workflow can delegate to declared subagents without changing provider entrypoints.

This is intentionally result metadata, not job lifecycle state. Apps such as CodeAlmanac still own durable jobs, retries, audit history, and cancellation policy. Yoke reports what happened at the harness boundary so callers can make honest decisions above it.

Future native workflow adapters can return `provider_native` when the provider actually owns the orchestration. That should not be inferred from `provider=\"claude\"` or `provider=\"codex\"`; it must come from the selected surface and its documented feature support.
