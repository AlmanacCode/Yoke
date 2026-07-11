# Goal doc refresh after goal-loop API

Date: 2026-07-04

Sources checked:

- https://developers.openai.com/codex/use-cases/follow-goals
- https://developers.openai.com/codex/cli/slash-commands
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/app/commands
- https://code.claude.com/docs/en/goal
- https://code.claude.com/docs/en/agent-sdk/overview

Current read:

Claude Code `/goal` is an evaluator loop. The user sets a completion condition, Claude works a turn, then a small fast model checks whether the condition is met. If not, Claude starts another turn instead of returning control. That behavior belongs to Claude Code's session runtime, not to a normal Python SDK `query()` call.

Codex CLI and app document `/goal` as thread-attached state with pause, resume, edit, and clear controls. The app shows goal progress above the composer. Codex app-server documents `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear` for the same persisted goal state surfaced by `/goal`.

Yoke's `goal_loop()` should therefore be a provider handle, not a polling implementation. It can start or attach goal-loop state on a provider surface and return a session handle, but it must not silently invent completion checks, retries, or app lifecycle semantics.

Design consequence:

- `RunOptions(goal=...)` remains bounded context.
- `SessionOptions(goal=...)` starts a goal-aware session.
- `GoalLoopOptions(goal=...)` explicitly asks for provider-owned continuation.
- `GoalRun` records the accepted goal and session handle.
- CodeAlmanac owns durable jobs above Yoke.
