# Codex app-server adapter slice

CodeAlmanac currently has a richer Codex app-server harness than Yoke. Moving CodeAlmanac onto Yoke before Yoke has an app-server surface would be a regression.

This slice adds `CodexAppServer` as a separate Yoke provider adapter with `surface="codex_app_server"`.

Implemented contract:

- starts `codex app-server --listen stdio://`,
- sends `initialize`,
- starts an ephemeral thread with `thread/start`,
- sends turns with `turn/start`,
- collects app-server notifications into Yoke `Event` values,
- exposes native mutable goals through `thread/goal/set` and `thread/goal/clear`,
- keeps the app-server process live for `Session` handles,
- implements one-shot `run()` as `start -> send -> close`.

The adapter is intentionally not the CodeAlmanac event model. Yoke owns provider execution and normalized-enough raw events. CodeAlmanac should later add a thin adapter that maps Yoke `Run` and `Event` values into CodeAlmanac `HarnessRunResult` and `HarnessEvent` values.

Current honesty notes:

- Native Codex goals do not work on ephemeral app-server threads. The first goal smoke failed with `ephemeral thread does not support goals`. Yoke now starts a non-ephemeral app-server thread when a Yoke `Goal` is attached so `thread/goal/set` can succeed.
- `stream()` is not a live async notification stream yet. The app-server protocol streams, but this adapter currently collects the turn result and then yields collected events.
- Declared Yoke subagents are not compiled into Codex app-server configuration yet.
- Codex app-server skills APIs exist, but Yoke folder skill roots are not wired into `skills/extraRoots/set` yet.
- Existing CodeAlmanac app-server notification mapping is still deeper than Yoke's first app-server mapper. Do not replace CodeAlmanac's adapter until Yoke covers the event details CodeAlmanac needs.
