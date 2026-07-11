# Provider-neutral event stream

Yoke exposes provider events as `Event` objects with a small public `EventKind` vocabulary and typed payload slots. The public contract is semantic, not a mirror of either provider's wire stream.

Codex app-server maps closely because its JSON-RPC notifications already describe turns, text deltas, tool lifecycle, server requests, token usage, goal updates, warnings, errors, and completion. Yoke maps those notifications into typed `Event` fields and keeps the original notification in `raw`.

Claude SDK maps through message objects, hook events, task events, and permission callbacks. Text, tool use, tool result, usage, hooks, background task events, and approval/user-input callbacks map cleanly. Claude does not expose the same native persisted goal lifecycle that Codex app-server exposes, so Yoke should not invent Claude `goal_updated` or `goal_cleared` stream events unless a real Claude surface starts emitting them.

Unknown provider messages should use `stream_event` or `unknown`, not provider-specific public kind strings. Provider-native names belong in `message`, typed payload fields, or `raw`. This keeps downstream code able to switch on `EventKind` without knowing provider implementation nouns.

Current public kinds are text and tool events, request events, context usage, provider session metadata, warnings/errors/done, hooks, rate limits, goal updates/clears, raw stream events, and unknown fallback. Provider-specific data stays available through `raw`.
