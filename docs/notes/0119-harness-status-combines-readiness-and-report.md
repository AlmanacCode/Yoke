# Harness status combines readiness and report

`Harness.status()` and `Harness.status_sync()` now return a `Status` object with:

- `readiness`: local install/auth/readiness for the selected surface
- `report`: Yoke's static declared capability report for the selected surface

This is the SDK-level form of the smoke JSON shape. It gives embedders such as CodeAlmanac one call for status screens without starting a provider run.

`Status.available` mirrors `Status.readiness.available`. Capability support still comes from `Status.report`; local readiness and declared capability are intentionally separate facts.
