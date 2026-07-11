# Readiness JSON smoke on 2026-07-04

Ran:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json
```

Result:

- `codex:codex_cli` was available with message `Logged in using ChatGPT`.
- `codex:codex_app_server` was available with message `Logged in using ChatGPT`.
- `codex:codex_python_sdk` was unavailable because `openai_codex` is not installed.
- `claude:claude_python_sdk` was unavailable because `claude_agent_sdk` is not installed.

This confirms the surface model in the current local environment. Codex provider auth exists, but the Python SDK surface is a separate optional dependency. Claude SDK support is also gated by the optional dependency. Future live smoke should install the relevant extras before treating SDK failures as adapter bugs.
