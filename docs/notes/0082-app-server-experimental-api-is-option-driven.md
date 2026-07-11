# App-server experimental API is option-driven

Codex app-server experimental API is negotiated once at `initialize`. Yoke should not silently opt every app-server process into experimental protocol.

`CodexOptions(experimental_api=True)` now drives initialization. Stable app-server sessions omit `capabilities.experimentalApi`; sessions/runs that request the feature initialize with `{ "capabilities": { "experimentalApi": true } }`.

A later turn cannot upgrade an already-stable app-server process. If a `RunOptions(provider=ProviderOptions(codex=CodexOptions(experimental_api=True)))` turn is sent through a session that was initialized without experimental API, Yoke raises a clear error asking the caller to start the session with `CodexOptions(experimental_api=True)`.

Per-turn provider options now override thread defaults for turn parameters. This matters for app-server fields like `collaborationMode`, which belong to `turn/start`, not only `thread/start`.

Design consequence: capability selection says which surface can satisfy a feature; provider options still decide whether the runtime instance actually opts into that feature.
