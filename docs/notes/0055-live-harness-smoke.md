# Live harness smoke evidence

This slice checked local harness availability without changing auth state.

Observed locally:

- `codex` exists at `/Users/rohan/.nvm/versions/node/v21.7.3/bin/codex`.
- `codex login status` reports `Logged in using ChatGPT`.
- `claude` exists at `/Users/rohan/.local/bin/claude`.
- `claude auth status` reports a logged-in `claude.ai` first-party account.
- `claude_agent_sdk` is not installed in the active Python environment.
- `openai_codex` is not installed in the active Python environment.

Implication:

The local CLIs are authenticated, but the Python SDK surfaces are not ready until optional extras are installed. This matches Yoke's model: readiness belongs to the selected surface, not only the provider.

Added `scripts/smoke_harnesses.py` as a manual smoke helper:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py
```

The default mode only checks readiness for:

- `codex:codex_cli`
- `codex:codex_app_server`
- `codex:codex_python_sdk`
- `claude:claude_python_sdk`

Actual agent execution is opt-in:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-cli
```

Provider turns can be slow, billable, and account-dependent, so live runs should remain explicit rather than part of the normal unit test suite.

Live Codex CLI result:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-cli
codex:codex_cli: ok: Logged in using ChatGPT
codex:codex_app_server: ok: Logged in using ChatGPT
codex:codex_python_sdk: missing: openai_codex is not installed
claude:claude_python_sdk: missing: claude_agent_sdk is not installed
codex_cli run: succeeded: yoke-smoke
```

This proves Yoke's Codex CLI adapter can execute a real local harness turn in the current environment.

Live Codex app-server result:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-app-server
codex:codex_cli: ok: Logged in using ChatGPT
codex:codex_app_server: ok: Logged in using ChatGPT
codex:codex_python_sdk: missing: openai_codex is not installed
claude:claude_python_sdk: missing: claude_agent_sdk is not installed
codex_app_server run: succeeded: yoke-app-smoke
```

This proves Yoke's Codex app-server adapter can execute a real local app-server turn in the current environment.
