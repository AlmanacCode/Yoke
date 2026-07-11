# 0090 - Plans dedupe required features

`surface_plan(...)` now normalizes required features once and preserves
first-seen order.

This keeps diagnostics stable when a caller combines option-derived features
with explicit feature requirements, for example:

```python
harness.plan(
    RunOptions(output_schema=Summary),
    features=(Feature.STRUCTURED_OUTPUT,),
)
```

The selected surface is unchanged, but `Plan.features`, `Plan.missing`, and
error messages no longer repeat the same feature.
