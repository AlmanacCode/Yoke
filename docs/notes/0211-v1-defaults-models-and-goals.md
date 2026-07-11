# V1 defaults: Codex app-server and Claude Python SDK

Yoke v1 should optimize for two product surfaces first:

- `Harness("codex", ...)` defaults to `codex_app_server`.
- `Harness("claude", ...)` defaults to `claude_python_sdk`.

Other surfaces remain tracked for capability reports and explicit overrides, but they are not the default product path.

This slice made model selection a common Yoke option instead of only provider-specific data:

- `Agent(model=...)` remains the agent default.
- `RunOptions(model=...)` overrides the agent model for one run.
- `SessionOptions(model=...)` overrides the agent model when starting a provider session.
- `Turn(model=...)` is available for lower-level session sends.

Codex app-server lowering:

- `thread/start` receives `model` from `SessionOptions.model` or `Agent.model`.
- `turn/start` receives `model` from `RunOptions.model`, then `Turn.model`, then `Session.agent.model`.
- Existing Codex app-server `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear` remain the native mutable goal path.

Claude Python SDK lowering:

- `ClaudeAgentOptions.model` receives `RunOptions.model` or `Agent.model`.
- `SessionOptions.model` flows into the Claude session's SDK options.
- `goal_loop()` sends `/goal <objective>` through the Claude Agent SDK slash-command path. Claude owns the Stop-hook evaluator and continuation loop. Yoke still does not claim Claude has Codex-style readable or mutable goal state.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_goals.py tests/test_capabilities.py` passed: 133 tests.
- `uv run ruff check src/yoke/options.py src/yoke/models.py src/yoke/surfaces.py src/yoke/adapters.py src/yoke/providers/claude.py src/yoke/providers/codex_app_server.py tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_capabilities.py` passed.

Current product completion estimate after this slice: about 50%. The core API and feature matrix are solid enough to start using locally, but full product confidence still needs live Codex app-server and Claude SDK smoke tests plus workflow/subagent/skill completion.
