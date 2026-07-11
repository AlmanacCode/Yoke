# Smoke readiness JSON is for agents

`scripts/smoke_harnesses.py` now supports `--json`.

The JSON mode is readiness-only. It checks each local surface and prints machine-readable records with `provider`, `surface`, `available`, `message`, and `fix`.

This is intentionally separate from live run flags. Real provider turns can be slow, billable, and auth-dependent; a JSON readiness mode should stay safe enough for future agents and CodeAlmanac integration checks to run before deciding which optional live smoke to request.

The human text mode remains the default because it is the fastest way to inspect local setup during development.
