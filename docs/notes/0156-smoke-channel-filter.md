# Smoke channel filter

Date: 2026-07-04

## Change

`scripts/smoke_harnesses.py` now accepts `--channel`.

Examples:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --channel app_server --capabilities
PYTHONPATH=src python scripts/smoke_harnesses.py --channel sdk --json
```

`--surface` and `--channel` intersect. This lets callers do exact selection when they know a surface, or broad exposure-path selection when they only care about CLI vs SDK vs app-server.

## Why this matters

CodeAlmanac integration will likely need quick local readiness checks. The integration should not need to hard-code every surface string just to ask "which app-server-backed harnesses are locally usable?" Channel filtering gives that operational vocabulary while preserving exact surface reporting.

## Boundary

`--channel` is only a smoke/readiness filter. It does not change feature selection semantics, and it does not make `sdk` imply support for a feature. Exact capability checks still come from `report()` and `fits()`.

## Live local check

Command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --channel app_server --capabilities
```

Result summary:

```text
matched=1
provider=codex
surface=codex_app_server
channel=app_server
available=true
message=Logged in using ChatGPT
```
