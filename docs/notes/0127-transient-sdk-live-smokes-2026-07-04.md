# Transient SDK live smokes on 2026-07-04

Yoke's base development environment did not have `openai_codex` or `claude_agent_sdk` installed. Transient `uv --with` runs proved both SDK adapters can become ready without permanently installing extras.

Combined readiness:

```bash
PYTHONPATH=src uv run --with openai-codex --with claude-agent-sdk python scripts/smoke_harnesses.py --json --capabilities --surface codex:sdk --surface claude:sdk
```

Observed:

- `codex_python_sdk`: available, `openai_codex available (0.1.0b2)`
- `claude_python_sdk`: available, `Claude authenticated via claude.ai`

The first Claude readiness attempt produced `{` as the message because `claude auth status` returns multi-line JSON and Yoke's generic command helper reports the first line. Yoke now parses Claude auth JSON and reports `Claude authenticated via claude.ai`.

Live Claude SDK smoke:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude
```

Result:

```text
claude:claude_python_sdk: ok: Claude authenticated via claude.ai
claude_python_sdk run: succeeded: yoke-claude-smoke
```

Live Codex Python SDK smoke:

```bash
PYTHONPATH=src uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk
```

Result:

```text
codex:codex_python_sdk: ok: openai_codex available (0.1.0b2)
codex_python_sdk run: succeeded: yoke-sdk-smoke
```

Design implication: readiness must distinguish base environment installation from surface support. Optional SDK surfaces can be unavailable in the base Yoke checkout while still working through normal Python package installation.
