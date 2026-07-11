# Smoke feature filter

Date: 2026-07-04

## Change

`scripts/smoke_harnesses.py` now accepts repeatable `--feature` filters.

Examples:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --feature readable_goal --json
PYTHONPATH=src python scripts/smoke_harnesses.py --channel app_server --feature readable_goal --capabilities
```

The filter intersects with `--surface` and `--channel`. A surface must support every requested feature according to Yoke's exact surface capability profile.

## Why this matters

CodeAlmanac integration should be able to ask operational questions without hard-coding provider knowledge:

- "Which local surfaces can read goals?"
- "Which app-server-backed surfaces support mutable goals?"
- "Which SDK surfaces support streaming?"

The answer should come from Yoke's capability matrix, then readiness should check whether the matching surfaces are locally usable.

## Boundary

`--feature` filters by declared capability metadata. It does not prove auth, installed binaries, or a working provider account. The smoke script still runs readiness checks after filtering.

## Live local check

Command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --feature readable_goal --capabilities
```

Result summary:

```text
matched=1
provider=codex
surface=codex_app_server
channel=app_server
available=true
message=Logged in using ChatGPT
readable_goal=native
```
