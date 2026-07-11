# Smoke surface filter uses Yoke aliases

`scripts/smoke_harnesses.py` now accepts `--surface PROVIDER:SURFACE`.

The filter is readiness-only. It narrows the readiness report without starting live provider turns. Explicit `--run-*` flags still name the live smoke to run.

The filter uses Yoke's normal `Harness` construction, so aliases work:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --surface codex:app
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --surface claude:sdk
```

The output still reports exact surface names such as `codex_app_server` and `claude_python_sdk`.

This gives future agents a cheap way to ask "is this exact surface available here?" without parsing the full smoke output or accidentally invoking a provider run.
