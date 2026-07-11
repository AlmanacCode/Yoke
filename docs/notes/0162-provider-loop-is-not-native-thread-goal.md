# Provider goal loops are not always native thread goals

Date: 2026-07-04

`Status.goal.mode` now distinguishes provider-owned goal loops from mutable
thread goal state.

`native_thread` means Yoke can talk to provider goal state through session
methods such as `get_goal`, `set_goal`, and `clear_goal`. Codex app-server is
the current example: it exposes `thread/goal/*` and also documents goal
continuation behavior.

`provider_loop` means the provider documents a keep-working goal loop, but Yoke
does not expose readable or mutable goal state through that surface. Claude CLI
and Codex CLI fit this shape. They have `/goal` behavior in the provider UX, but
Yoke's current runnable CLI adapters remain bounded run wrappers.

This matters because goal loops are the dangerous primitive. A bounded
`RunOptions(goal=...)` or `SessionOptions(goal=...)` should not imply "keep
working until stopped." If a future Yoke adapter can truly drive a provider goal
loop, it should add an explicit execution verb rather than hiding that behavior
inside `run()`.
