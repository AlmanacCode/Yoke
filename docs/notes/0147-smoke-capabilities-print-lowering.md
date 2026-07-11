# Smoke capabilities print lowering highlights

Date: 2026-07-04

`scripts/smoke_harnesses.py --capabilities` now has useful human output.

Before this slice, `--capabilities` only affected JSON output. The JSON report already includes the full `SurfaceReport`, including feature evidence and lowering text. Human output still only printed readiness, so a local inspection did not show how a provider surface lowers Yoke concepts.

Non-JSON smoke output now prints a compact capability section per surface. It includes only features with `lowering` text. This keeps the terminal readable while surfacing the ambiguous cases: subagents, skills, workflows, goals, and native provider collaboration events.

Example shape:

```text
codex:codex_app_server: ok: Logged in using ChatGPT
  capabilities: codex:codex_app_server
    readable_goal: native
      lowering: Session.get_goal calls app-server thread/goal/get.
```

Design implication: JSON remains the full machine-readable matrix. Human smoke output should show the high-signal rows that explain provider/surface behavior without making users parse the entire capability table.
