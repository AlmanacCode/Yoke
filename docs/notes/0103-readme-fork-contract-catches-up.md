# README fork contract catches up

Yoke's implementation now supports provider-native fork on three runnable surfaces:

- `claude_python_sdk`: full-session resume-fork using `provider_session_id`.
- `codex_python_sdk`: `thread_fork` on the same live SDK client.
- `codex_app_server`: `thread/fork` through the app-server process.

The README previously only described Codex app-server fork and said Claude/Codex SDK fork semantics were still unknown. That was stale after the provider-session-id and SDK ownership slices.

The public docs now describe the surface-specific fork contract and the two-id model: `Session.id` is Yoke's live key, while `Session.provider_session_id` is the provider-persisted conversation id. Tests also pin Codex SDK fork and interrupt capability notes so future matrix edits do not silently drift.
