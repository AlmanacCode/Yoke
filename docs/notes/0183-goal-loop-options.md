# Goal loop options are separate from ordinary goals

Date: 2026-07-04

Yoke now treats goal loops as a separate planning request from ordinary goals.

`Goal` means "give this objective to the bounded run or session." `RunOptions(goal=...)`, `SessionOptions(goal=...)`, and `Agent(goal=...)` require `Feature.GOAL`. Those options do not imply that the provider should keep working after the current run.

`GoalLoopOptions(goal=...)` means "select a provider surface that exposes a native keep-working goal loop." It requires `Feature.GOAL_LOOP`. This protects CodeAlmanac's own job/run lifecycle from accidentally becoming "provider keeps working until stopped."

This distinction matters because Codex and Claude expose goal behavior at different levels:

- Codex app-server exposes persisted thread goal state through `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear`.
- Codex app and CLI document `/goal` as a persistent objective that can continue across turns.
- Claude Python SDK has no native goal state in the current docs; Yoke compiles goals into task context.
- Claude CLI documents `/goal` as a loop/evaluator surface, but it is not the same as Claude Python SDK options.

The capability matrix must stay surface-specific. "Codex supports goals" is too vague; "codex_app_server supports mutable/readable goals and native goal loops" is the useful statement. "Claude supports workflows" is also too vague; Claude TypeScript SDK has native dynamic workflows, while Claude Python SDK is the runnable Yoke adapter today.

The current API is intentionally only a planner/readiness guardrail. Yoke does not yet implement a portable autonomous goal runner. A future runner should be explicit, probably session-oriented, and should never be triggered by `RunOptions(goal=...)` alone.
