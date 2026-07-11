# Session turns accept run options

`Session.run(...)` and `Session.stream(...)` now accept `RunOptions`.

The important API shape is:

```python
session = await harness.start()
result = await session.run(
    "Return a JSON summary.",
    RunOptions(output_schema=Summary),
)
```

This keeps one-shot and multi-turn usage symmetric. `RunOptions` means "options for this provider turn," not only "options for a top-level harness run."

Provider behavior is still surface-specific:

- Codex CLI sessions pass per-turn permissions, effort, goal resolution, and output schema into the resumed `codex exec` turn.
- Codex Python SDK sessions pass per-turn permissions, effort, goal resolution, and output schema into `thread.run`; streaming turns pass permissions, effort, and goal resolution.
- Codex app-server sessions pass per-turn permissions and output schema into `thread/sendUserInput` through the app-server turn params.
- Claude live sessions accept the same method signature, but most run options remain fixed at `ClaudeSDKClient` construction time. This is an honest surface limitation, not a different public API.

Goals follow the existing policy: `RunOptions.resolve_goal(session.goal)` controls whether a turn inherits the session goal, overrides it, or disables it with `inherit_goal=False`.

The provider port changed from `send(session, turn)` to `send(session, turn, options)` and from `stream(session, turn)` to `stream(session, turn, options)`. Test adapters should use the new signature.
