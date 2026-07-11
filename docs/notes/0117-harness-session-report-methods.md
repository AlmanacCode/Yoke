# Harness and Session expose capability reports

`Harness.report()` and `Session.report()` now return the same JSON-friendly `SurfaceReport` as `report_for(...)`.

This keeps the main object API coherent:

- `capabilities()` returns the Python capability matrix
- `profile()` returns the rich planning profile
- `report()` returns a serialization-friendly status object
- `fit()` and `plan()` answer feature-selection questions

The method is intentionally read-only. It does not check local readiness or start a provider run. It reports Yoke's declared capability matrix for the selected provider surface.
