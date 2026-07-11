# Goal surface modes

Yoke now exposes `Status.goal` so applications can inspect goal behavior before
starting a run. The report separates four cases:

- `native_thread`: the provider surface exposes goal state on a live session.
- `compiled_context`: Yoke passes the goal as context, but does not own a
  keep-working loop.
- `unsupported`: the provider surface cannot accept Yoke goals.
- `unknown`: a custom surface has no declared goal metadata.

This exists because Codex and Claude use the word "goal" differently across
surfaces. Codex app-server has thread goal methods. Claude Code `/goal` is a
session-scoped continuation loop evaluated after each turn. Claude Agent SDK
`taskBudget` is token pacing, not goal-state management.

Yoke now models that separately as `Feature.GOAL_LOOP`. `Feature.GOAL` means a
goal value can affect a run or session. `Feature.GOAL_LOOP` means the surface
documents provider-native continuation after a turn. `Status.goal.loop` exposes
that support level and `Status.goal.auto_continues` is true for native loop
surfaces.

This keeps the normal SDK contract conservative: constructing `Goal(...)` and
passing it to `harness.run(...)` still means a bounded call unless the chosen
surface explicitly documents a goal loop. CodeAlmanac can use
`Feature.GOAL_LOOP` to avoid accidentally changing its job unit from "one run"
to "keep working until an external stop condition passes."

Sources:

- https://developers.openai.com/codex/app-server
- https://code.claude.com/docs/en/goal
- https://code.claude.com/docs/en/agent-sdk/typescript
