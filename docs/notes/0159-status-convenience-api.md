# Status convenience API

Date: 2026-07-04

## Change

`Status` now exposes common integration fields directly:

```python
status.provider
status.surface
status.channel
status.support_for(Feature.READABLE_GOAL)
status.supports(Feature.READABLE_GOAL)
```

The nested objects remain available:

```python
status.readiness
status.report
```

## Why this matters

Embedding apps such as CodeAlmanac need a small status object that combines local readiness and declared capability metadata. They should not need to traverse `status.report.features` for common checks.

`Status.supports(...)` uses the same support semantics as `Capabilities.supports(...)`: `native`, `compiled`, and `emulated` count as support; `unknown` and `unsupported` do not.

## Boundary

`Status` remains one-surface status. Provider-wide views should use `matrix_for(...)` for capability metadata and the smoke script for readiness across multiple surfaces.
