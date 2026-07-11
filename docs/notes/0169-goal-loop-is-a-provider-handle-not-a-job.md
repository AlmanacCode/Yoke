# Goal loop is a provider handle, not a job

Date: 2026-07-04

Yoke now exposes `Harness.goal_loop(GoalLoopOptions(...))`.

The method returns `GoalRun`, a small handle containing:

- provider and surface
- accepted `Goal`
- provider `Session`
- `auto_continues`
- setup status and failure metadata

This is deliberately not a durable job record. Yoke starts or attaches provider-owned goal-loop state and returns control to the caller. CodeAlmanac and other applications still own queueing, retries, audit logs, cancellation policy, completion criteria, and user-visible run lifecycle.

The first built-in runnable implementation is Codex app-server. It starts a thread with the requested goal and returns the session handle. The CLI surfaces can document `/goal` while still being unsupported as programmatic Yoke `goal_loop()` targets, because Yoke cannot safely control an interactive slash-command loop as a typed SDK operation.

Normal `RunOptions(goal=...)` and `SessionOptions(goal=...)` remain bounded context. `GoalLoopOptions` is the explicit opt-in to provider-owned continuation.
