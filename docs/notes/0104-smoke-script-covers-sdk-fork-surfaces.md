# Smoke script covers SDK fork surfaces

`scripts/smoke_harnesses.py` now has opt-in smoke flags for the fork surfaces Yoke has wired:

- `--run-codex-app-fork`
- `--run-codex-sdk-fork`
- `--run-claude-fork`

The default mode remains readiness-only because provider turns can be slow, billable, and auth-dependent. The fork smokes first run a tiny source turn because both Codex app-server and Claude Python fork need a materialized provider-side session before branching.

The Claude smoke uses `Run.session.provider_session_id` after the source turn, not the original Yoke-local `Session.id`, matching the two-id model.
