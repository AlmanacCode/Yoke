# Goal read API

Yoke exposes provider goal operations on `Session`:

```python
goal = await session.get_goal()
session = await session.set_goal(Goal("Finish safely."))
session = await session.clear_goal()
```

There are sync twins:

```python
goal = session.get_goal_sync()
session = session.set_goal_sync(Goal("Finish safely."))
session = session.clear_goal_sync()
```

This is intentionally session-scoped. Native goals are thread state, not a property of a one-shot run.

Codex app-server maps `get_goal()` to `thread/goal/get`, which returns the same persisted goal state surfaced by `/goal` in the TUI.

Codex rejects native goals on ephemeral app-server threads. Yoke app-server sessions are persistent by default so callers can set a goal after `start()`. Callers that explicitly pass `CodexAppServer(ephemeral=True)` are opting out of later native goal support for that thread.

Claude and Codex CLI do not expose native readable mutable goals through the surfaces Yoke currently uses. Those adapters raise `UnsupportedFeature` for `get_goal`, `set_goal`, and `clear_goal`. Their goal support remains prompt-compiled.

This keeps the dangerous part explicit:

- A prompt-compiled goal is instruction text inside one run or session.
- A native Codex app-server goal is provider-owned thread state that can survive turns and be read, updated, or cleared.
