# Readiness JSON smoke on 2026-07-04

Command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --capabilities
```

Observed local readiness:

- `codex_cli`: available, `Logged in using ChatGPT`
- `codex_app_server`: available, `Logged in using ChatGPT`
- `codex_python_sdk`: unavailable, `openai_codex is not installed`
- `claude_python_sdk`: unavailable, `claude_agent_sdk is not installed`

The JSON readiness output now includes static capability reports with evidence URLs. This keeps two facts separate:

- readiness says whether this machine can use a surface right now;
- capabilities say what Yoke believes the surface supports when installed and authenticated.

This matters for CodeAlmanac integration because it can show a user that Codex app-server is locally usable while Claude SDK support only needs an optional package/auth setup, without starting a billable provider turn.

Live Codex app-server smoke:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
```

Result:

```text
codex:codex_app_server: ok: Logged in using ChatGPT
codex_app_server run: succeeded: yoke-app-smoke
```
