# README teaches surface modes

The README now documents the three user-facing surface modes:

- exact names, such as `codex_app_server`
- `surface="auto"`, which leaves selection to required capabilities
- friendly aliases, such as `codex:app` and `claude:sdk`

The docs also mention the `all` extra because embedded callers often want both provider SDKs installed while prototyping.

This keeps the public story aligned with the code. The friendly examples do not replace exact capability reporting; exact surface names remain visible in plans, runs, sessions, readiness, and events.
