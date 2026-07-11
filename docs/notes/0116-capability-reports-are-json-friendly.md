# Capability reports are JSON-friendly

Yoke now exposes `report_for(...)` and `reports_for(...)`.

The existing `Profile` model remains the rich runtime/planning object. It carries `Capabilities` keyed by `Feature` enum values. That is useful in Python, but awkward for integrations that want to serialize or display capability data.

`SurfaceReport` is the integration shape:

```python
report = report_for("codex", "app")
report.model_dump()
```

The report uses plain strings for `provider`, `surface`, `feature`, and `support`. Surface aliases are accepted on input, and reports always return exact surface names.

This is intended for CodeAlmanac integration, CLI/status displays, and future docs generation. It does not replace `Profile`, `Fit`, or `Plan`; those remain the planning objects.
