# Codex app-server live streaming

Codex app-server sends structured notifications while a turn is running. Yoke used to read the full turn into a `Run` and then replay the stored events from `Session.stream(...)`.

That was safe but wrong for this surface. It flattened the app-server into CLI-like behavior.

Yoke now has one shared turn reader:

- `read_turn(...)` collects the whole turn for `send()` and `run()`.
- `read_turn_step(...)` reads one notification step for `stream()`.

Both paths use the same notification mapper, so streaming and collected runs stay consistent.

Current behavior:

- `Session.stream(...)` starts a Codex app-server turn.
- It yields `provider_session` immediately after `turn/start`.
- It then yields mapped events as app-server notifications arrive.
- It yields `done` when the root turn completes.

This makes `codex_app_server` streaming native in the capability map.

Codex CLI remains non-native for streaming because `codex exec --json` is a process output surface, not the app-server notification protocol.

