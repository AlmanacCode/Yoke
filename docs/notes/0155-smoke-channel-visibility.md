# Smoke output channel visibility

Date: 2026-07-04

## Change

`scripts/smoke_harnesses.py` now shows the provider exposure channel in readiness output.

Human output now looks like:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
```

Capability summaries now look like:

```text
  capabilities: codex:codex_app_server [app_server]
```

JSON readiness records now include:

```json
{
  "provider": "codex",
  "surface": "codex_app_server",
  "channel": "app_server"
}
```

## Why this matters

Yoke's hard problem is provider-surface specificity. A smoke result that only says `codex_app_server` is precise but still makes the reader mentally map it to the exposure path. Showing `[app_server]`, `[sdk]`, or `[cli]` makes operational reports readable at a glance.

This is useful before CodeAlmanac integration because a worker or lifecycle command can display readiness without needing users to know every exact surface name.

## Boundary

The smoke script still filters by exact provider/surface. Channel is displayed; it is not yet a CLI filter for the smoke script.

## Live local check

Command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --surface codex:app --capabilities
```

Result summary:

```text
provider=codex
surface=codex_app_server
channel=app_server
available=true
message=Logged in using ChatGPT
capabilities.channel=app_server
```
