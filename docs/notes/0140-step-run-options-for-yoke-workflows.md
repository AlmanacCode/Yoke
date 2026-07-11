# Workflow steps can override run options

Date: 2026-07-04

Yoke workflows now support per-step run options with `Step(run=...)`.

The shape is intentionally Yoke-owned. Codex public workflow docs are usage patterns for the app, CLI, IDE, and cloud rather than a portable SDK workflow primitive. Codex SDK exposes thread start/resume and repeated `run(...)` calls. Codex app-server exposes richer thread and turn primitives, including persisted thread goals. Claude Agent SDK subagents cover turn-level delegation, while the native `Workflow` tool is TypeScript-SDK-specific for large dynamic orchestration.

Design choice: Yoke workflows stay as a small DAG over provider turns. Workflow-level `WorkflowOptions(run=RunOptions(...))` sets defaults. A step can override those defaults with `Step(run=RunOptions(...))` or a YAML-style `run:` mapping from folder workflows.

This supports examples like:

- one verification step using read-only permissions while earlier steps can write;
- one step using a step-specific `Goal` while the rest inherit the workflow goal;
- one step needing a different output schema;
- provider-specific options attached only to the step that needs them.

Planning now inspects per-step run options before surface selection. If a step declares a goal or structured output requirement, `surface="auto"` can choose a surface that satisfies the workflow instead of selecting too early from only workflow-level defaults.

Current evidence checked:

- Codex workflows page describes practical app/CLI/IDE/cloud workflow patterns.
- Codex SDK docs show thread start/resume and repeated runs.
- Codex app-server docs show `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear` as real persisted goal state.
- Claude Agent SDK docs say dynamic workflows use the TypeScript `Workflow` tool for large orchestration outside conversation context.

Next pressure test: decide whether folder workflow saving should emit `run:` frontmatter for step options, and whether `Step.run` should eventually become a typed model without creating circular imports.
