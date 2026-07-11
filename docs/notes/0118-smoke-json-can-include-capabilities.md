# Smoke JSON can include capabilities

`scripts/smoke_harnesses.py --json --capabilities` now includes Yoke's static `SurfaceReport` inside each readiness record.

Readiness and capabilities answer different questions:

- readiness says whether the local machine currently appears able to use the surface
- capabilities say what Yoke believes the surface supports

The command remains non-live. It does not start Codex or Claude turns unless an explicit `--run-*` flag is passed. `--capabilities` only adds declared metadata from `Harness.report()`.

This shape is useful for CodeAlmanac integration because a status command can show both "installed/authenticated here" and "feature support if available" without parsing provider-specific output or running a billable agent turn.
