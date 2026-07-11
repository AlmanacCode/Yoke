# 0089 - Plans expose direct diagnostics

`Plan` now exposes the selected provider, surface, and missing features directly:

```python
plan = harness.plan(options)
plan.provider
plan.surface
plan.missing
```

Callers should not need to know that Yoke scores `Fit` objects internally just
to answer "what surface would this use?" or "why can this not run here?".

`plan.fit` and `plan.candidates` remain available for deeper diagnostics and
surface selection explanations.
