# Workflow options declare workflow features

Date: 2026-07-04

`WorkflowOptions` now exposes `features(inherited_goal=None)`.

Workflow execution always implies `Feature.WORKFLOW`. If workflow-level `output_schema` is set, or the embedded `run` options imply structured output, workflow execution also implies `Feature.STRUCTURED_OUTPUT`.

`Harness.workflow(...)` now asks `WorkflowOptions` for implied features and passes each one through `Harness.require(...)` before invoking the Yoke workflow runner.

The option model pattern is now consistent:

- `RunOptions.features(...)` owns run option feature requirements.
- `SessionOptions.features(...)` owns session-start feature requirements.
- `WorkflowOptions.features(...)` owns workflow feature requirements.

This keeps feature requirements close to the knobs that create them.
