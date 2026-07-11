# 0244 - Smoke plan and SDK coverage

Date: 2026-07-04

Yoke's smoke script now has a first-class smoke matrix mode.

## What changed

- `scripts/smoke_harnesses.py --plan` and `--list` print smoke commands without running providers.
- `--plan --json` returns a machine-readable `smokes` array.
- Plan output respects existing `--surface`, `--channel`, and `--feature` filters.
- Each record names `kind`, `provider`, `surface`, `channel`, `feature`, `safety`, and `command`.
- Codex Python SDK now has an opt-in live stream smoke flag: `--run-codex-sdk-stream`.
- Claude Python SDK now has an opt-in permission callback smoke flag: `--run-claude-permissions`.
- Codex app-server stream smoke now reuses the generic stream smoke runner.

## Why

The old smoke surface had good flags, but agents had to read the script or scattered notes to know what was safe, what was live, and what coverage existed per provider surface. The smoke script now explains its own matrix.

## Verified

Focused unit tests passed:

```bash
PYTHONPATH=src uv run pytest tests/test_smoke_harnesses.py
```

Result: 26 passed.

Focused ruff passed:

```bash
PYTHONPATH=src uv run ruff check scripts/smoke_harnesses.py tests/test_smoke_harnesses.py
```

Result: all checks passed.

Non-provider CLI smoke passed:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --plan --json --surface codex:sdk --surface claude:sdk
```

Result: JSON included safe readiness rows and opt-in live rows for Codex Python SDK stream plus Claude permissions.

## Still live-only

These flags are discoverable but still need actual provider runs to prove account-local behavior:

- Codex Python SDK stream: `--run-codex-sdk-stream`
- Claude permission callback: `--run-claude-permissions`
- Existing live smokes for request handling, workflows, subagents/collab, fork, rename, and goals

The unit tests prove command planning and fake harness wiring. They do not prove current auth, optional package availability, provider API behavior, or live event contents.
