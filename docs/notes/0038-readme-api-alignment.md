# README API alignment

Date: 2026-07-04

The README now describes the public surfaces added during the integration-pressure slices:

- `Run.status` and `Run.failure`
- `Harness.check()` readiness
- `Harness.capabilities()`
- workflow DAG dependencies and `WorkflowOptions.concurrency`
- failed workflow behavior through `WorkflowRun.status`

The README should stay usage-shaped rather than exhaustive. Detailed design notes remain in `docs/notes/`.

This matters because Yoke's selling point is "a readable SDK that also matches folder structure." If the README teaches an older one-shot-only model, users will miss the provider-surface and embedding contracts that make Yoke different from a thin CLI wrapper.
