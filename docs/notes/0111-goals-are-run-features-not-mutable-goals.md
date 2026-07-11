# Goals are run features, not mutable goals

`RunOptions.features(...)` and `SessionOptions.features(...)` now declare `Feature.GOAL` when a goal is explicitly set or inherited from the agent/session.

This is intentionally separate from `Feature.READABLE_GOAL` and `Feature.MUTABLE_GOAL`.

A run goal means the adapter can receive goal context for the turn or session. That may be native, compiled into prompts, or unsupported depending on the surface. Mutable/readable goals mean the provider exposes stateful goal operations such as get, set, or clear.

The distinction keeps Codex CLI useful. Codex CLI supports compiled goals, so a normal run with an inherited goal can stay on `codex_cli`. It should not jump to `codex_app_server` unless the caller asks for native mutable or readable goal behavior.

Yoke's harness/session planner now keeps the provider default surface for the plain `Feature.GOAL` case when that default satisfies goals. It still selects richer surfaces for other feature requests such as structured output, model listing, collaboration mode, readable goals, and mutable goals. Direct `select_profile(...)` still answers "which surface is best for these features" rather than "what should this default harness do."
