# Codex surfaces are not equivalent

Codex should not be treated as one feature surface. Yoke needs a provider plus surface capability matrix because `codex_cli`, `codex_python_sdk`, and `codex_app_server` expose different primitives.

The Codex Python SDK exposes `AsyncCodex.thread_start`, `AsyncCodex.thread_resume`, and `AsyncCodex.thread_fork`, and its `AsyncThread` exposes `run`, `turn`, `read`, `set_name`, and `compact`. Yoke can therefore support native SDK session fork by keeping forked sessions on the same live SDK client that created the source thread.

The app-server remains the deepest Codex surface. The SDK source wraps app-server calls, but the generated/client layer includes lower-level operations such as `thread/goal/set`, `thread/goal/clear`, `thread/compact/start`, `turn/start`, and `turn/interrupt`. Some of those are only exposed through private client helpers or app-server calls, not as stable high-level SDK methods.

Implication: Yoke should keep using feature support per concrete surface. A Codex SDK feature should not imply the CLI has it, and an app-server feature should not imply the SDK has a stable public method for it.
