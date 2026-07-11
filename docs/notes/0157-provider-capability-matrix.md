# Provider capability matrix

Date: 2026-07-04

## Change

Yoke now has a provider-level capability report:

```python
matrix = matrix_for("codex", channel=Channel.APP_SERVER, runnable=True)
```

The result is a `ProviderReport` with:

- `provider`
- optional `channel` filter
- optional `runnable` filter
- `surfaces`, a tuple of existing `SurfaceReport` objects

## Why this exists

`report_for(...)` and `reports_for(...)` are useful low-level helpers, but CodeAlmanac integration will likely want a single JSON-friendly object for status pages, diagnostics, and provider selection. `matrix_for(...)` gives that without introducing a registry or duplicating capability logic.

## Boundary

`matrix_for(...)` is metadata. It does not check live auth or local availability. Use `Harness.check()` or `scripts/smoke_harnesses.py` for readiness.

## Example use

```python
matrix = matrix_for("codex", channel="app_server", runnable=True)
for surface in matrix.surfaces:
    print(surface.surface, surface.channel)
```

This should be the starting point for integration code that needs to explain why Yoke selected one surface over another.
