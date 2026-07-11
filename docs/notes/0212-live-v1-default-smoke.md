# Live v1 default smoke

Date: 2026-07-04.

This slice live-tested the v1 product defaults:

- `Harness("codex", ...)` -> `codex_app_server`.
- `Harness("claude", ...)` -> `claude_python_sdk`.

Readiness results:

- Codex app-server was available through existing ChatGPT auth: `Logged in using ChatGPT`.
- Claude SDK was initially unavailable because `claude_agent_sdk` was not installed.
- `uv sync --extra claude` installed `claude-agent-sdk==0.2.110` and related dependencies.
- Claude SDK then reported available through existing Claude.ai auth: `Claude authenticated via claude.ai`.

Live run results:

- Codex app-server default run succeeded.
  - Surface: `codex_app_server`.
  - Output: `Yoke Codex app-server smoke ok.`
  - Events: 19.
  - Provider session id: `019f2df4-aa98-7f70-a81d-599addf7abf4`.
- Claude Python SDK default run succeeded.
  - Surface: `claude_python_sdk`.
  - Output: `Yoke Claude SDK smoke ok.`
  - Events: 9.
  - Provider session id: `9b377591-30cd-4964-9c1a-1e2b9050ef05`.

Live goal results:

- Codex app-server native mutable goal path succeeded.
  - `SessionOptions(inherit_goal=True)` set the agent goal on thread start.
  - `session.get_goal_sync()` read back `Keep the Yoke goal smoke bounded and read-only.`
  - `session.clear_goal_sync()` cleared the goal.
- Claude Python SDK goal loop succeeded through the SDK slash-command path.
  - Yoke sent `/goal Reply that the Yoke Claude goal smoke is set, then stop.`
  - The returned raw output was `The Yoke Claude goal smoke is set.`

Product finding:

- `Status` originally required `status.readiness.message`; smoke usage naturally tried `status.message`.
- Yoke now exposes `Status.message` and `Status.fix` as direct convenience properties.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_readiness.py tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_goals.py tests/test_capabilities.py` passed: 159 tests.
- `uv run ruff check src/yoke/status.py tests/test_readiness.py src/yoke/options.py src/yoke/models.py src/yoke/surfaces.py src/yoke/adapters.py src/yoke/providers/claude.py src/yoke/providers/codex_app_server.py tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_capabilities.py` passed.

Updated product estimate: about 58%. The default run path and goal path are now live-proven for both v1 surfaces. Remaining high-value work is feature completion for workflows, subagents, skills, and richer event/request ergonomics.

## Follow-up ergonomics patch

Two sidecar agents reviewed Claude SDK support and Codex app-server result ergonomics.

Claude finding:

- The Claude Agent SDK docs support slash commands as prompt strings when dispatchable.
- The Python SDK does not expose the native TypeScript `Workflow` tool in its documented tool input/output set.
- Yoke should describe Claude Python SDK goal loops as `/goal` slash-command-backed, not as readable/mutable Codex-style goal state.

Codex finding:

- `Run.provider_session_id` was a property, not a method.
- It was not serialized by `model_dump()`.
- One-shot Codex app-server runs exposed the provider id through events, but `result.session.provider_session_id` stayed `None`.

Patch:

- `Run.provider_session_id` is now a Pydantic computed field and appears in `model_dump()`.
- Codex app-server one-shot runs now copy the thread id into `result.session.provider_session_id`.
- `Status.message` and `Status.fix` now proxy readiness fields directly.

Verification after the patch:

- `PYTHONPATH=src uv run pytest tests/test_results.py tests/test_readiness.py tests/test_codex_app_server_params.py tests/test_claude_options.py tests/test_goals.py tests/test_capabilities.py` passed: 165 tests.
- `uv run ruff check src/yoke/models.py src/yoke/providers/codex_app_server.py src/yoke/status.py tests/test_results.py tests/test_readiness.py` passed.
- Live Codex app-server re-smoke confirmed `result.provider_session_id`, `result.session.provider_session_id`, and `result.model_dump()["provider_session_id"]` all matched.
