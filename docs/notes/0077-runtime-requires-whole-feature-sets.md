# Runtime requires whole feature sets

Yoke execution paths should select or validate a surface against the complete feature set for an operation. They should not loop over one required feature at a time.

A run, stream, session start, or workflow may imply multiple features through its options. The selected surface must satisfy the whole set at once, because provider support is surface-specific and combinations matter.

`Harness.require()` and `Session.require()` now use the same `surface_plan(...).raise_for_status()` path that diagnostic callers use. This keeps planning, runtime selection, and runtime failure messages aligned.

The concrete bug this prevents: a session stream with structured output needs both `streaming` and `structured_output`. The operation should choose one surface that supports both, not accidentally select for streaming first and validate structured output later as a separate concern.
