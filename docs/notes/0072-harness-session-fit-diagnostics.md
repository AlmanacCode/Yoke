# Harness and Session expose fit diagnostics

Date: 2026-07-04

`Harness` and `Session` now expose object-level diagnostics:

- `fit(*features)` returns a `Fit` for the selected/resolved surface.
- `fits(*features, runnable=True)` returns ranked candidate profiles for the provider.

The global `fits_for(provider, ...)` remains useful for conceptual planning. Object-level `fits(...)` defaults to runnable surfaces because a `Harness` or `Session` is a run-capable object, matching `require(...)` defaults.

This makes surface reasoning available from the object users already hold:

```python
harness.fit(Feature.MODELS)
harness.fits(Feature.MODELS)
```

The distinction matters:

- `fit` answers whether this selected surface can do something.
- `fits` answers which surfaces for this provider would do it best.
