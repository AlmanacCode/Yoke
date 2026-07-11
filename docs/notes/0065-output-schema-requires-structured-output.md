# Output schema requires structured output

Date: 2026-07-04

Yoke now treats `RunOptions(output_schema=...)` as an implied feature requirement.

Rules:

- `Harness.run(..., RunOptions(output_schema=...))` requires `Feature.STRUCTURED_OUTPUT`.
- `Session.run(..., RunOptions(output_schema=...))` requires `Feature.STRUCTURED_OUTPUT`.
- `Session.stream(..., RunOptions(output_schema=...))` requires both `Feature.STREAMING` and `Feature.STRUCTURED_OUTPUT`.
- Plain `run(...)` without an output schema does not auto-select a richer surface.

This keeps the default one-shot path cheap, but makes explicit structured-output asks safe on pinned or future surfaces. If a caller pins a surface with unknown or unsupported structured output, Yoke fails before adapter invocation. If no surface is pinned, Yoke selects the best runnable surface that supports structured output.
