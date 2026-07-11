# Goal loop capability

Yoke now has `Feature.GOAL_LOOP` in addition to `Feature.GOAL`.

`Feature.GOAL` means a `Goal` value can be attached to an agent, run, or
session. The surface may compile it into prompt context, store it as provider
thread state, or reject it.

`Feature.GOAL_LOOP` means the provider surface documents native continuation
after one turn. This is the dangerous lifecycle-changing behavior: the unit can
become "keep working until the objective is met, paused, cleared, budget-limited,
or blocked."

Current interpretation:

- Claude SDK: `goal` is compiled context; no SDK goal loop.
- Claude CLI: `/goal` is a native session-scoped evaluator loop.
- Codex CLI: `/goal` is documented as native interactive behavior, but Yoke's
  direct adapter still uses bounded `codex exec` calls.
- Codex Python SDK: no native goal loop method exposed.
- Codex app-server: exposes the persisted goal state used by `/goal` through
  `thread/goal/*`; Yoke treats the provider surface as native for goal loops,
  but CodeAlmanac still needs to decide whether its own job lifecycle should
  delegate continuation.

This lets a caller require `Feature.GOAL` for "please keep this objective in
context" and require `Feature.GOAL_LOOP` only when it truly wants provider-owned
continuation.

Sources:

- https://developers.openai.com/codex/use-cases/follow-goals
- https://developers.openai.com/codex/app-server
- https://code.claude.com/docs/en/goal
