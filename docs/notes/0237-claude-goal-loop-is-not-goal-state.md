# Claude goal loop is not goal state

The native-reference pass in `0234-native-workflow-goal-reference-check.md` found no public `Goal` model or persisted goal API in the local Claude Agent SDK Python clone.

Yoke still supports Claude `goal_loop` because the Claude provider adapter has a concrete path: send `/goal <objective>` through the Python SDK prompt stream. That is provider-owned slash-command behavior, not Codex-style readable or mutable thread goal state.

The capability matrix now keeps these concepts separate:

- `goal` on Claude SDK is `compiled`: Yoke goal context enters the system prompt/task budget.
- `goal_loop` on Claude SDK is `native`: the provider owns the `/goal` loop behavior once invoked.
- `readable_goal` and `mutable_goal` on Claude SDK are `unsupported`.
- `goal`/`mutable_goal`/`readable_goal` on Codex app-server remain native thread state.

This distinction is important for API ergonomics. `await harness.goal_loop(...)` can work for Claude, but `await session.get_goal()` and `await session.set_goal(...)` must not be implied for Claude.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_readiness.py`
- `PYTHONPATH=src uv run ruff check src/yoke/surfaces.py src/yoke/status.py tests/test_capabilities.py tests/test_readiness.py`
