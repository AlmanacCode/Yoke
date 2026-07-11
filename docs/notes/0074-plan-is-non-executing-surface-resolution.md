# Plan is non-executing surface resolution

Date: 2026-07-04

Yoke now has a public `Plan` model and object-level planning helpers:

```python
plan = harness.plan(RunOptions(output_schema=Summary))
plan.profile.surface
plan.ok
plan.fit.missing
```

`Plan` combines:

- the required `Feature` tuple;
- the selected `Fit` that mirrors `require(...)` behavior;
- ranked candidate fits for diagnostics.

Planning does not start an adapter, subprocess, SDK client, or model run. It only resolves capability pressure against the surface matrix.

Rules:

- If a harness/session has no explicit surface and features are required, `plan(...)` selects the best runnable surface by default.
- If a surface is explicit, `plan(...)` validates that surface and reports missing features instead of silently switching.
- `Plan.ok` means the selected fit satisfies all required features.
- `Plan.profile` is the selected profile.

This lets applications inspect a run/session/workflow before executing it without duplicating Yoke's surface-selection logic.
