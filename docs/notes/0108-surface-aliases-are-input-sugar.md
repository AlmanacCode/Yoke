# Surface aliases are input sugar

Yoke now accepts short surface aliases on user-constructed runtime handles.

The aliases are provider-aware:

```python
Harness(provider="codex", surface="app", ...)
Harness(provider="codex", surface="sdk", ...)
Harness(provider="codex", surface="cli", ...)
Harness(provider="claude", surface="sdk", ...)
Harness(provider="claude", surface="cli", ...)
```

`codex:app` normalizes to `codex_app_server`. `codex:sdk` normalizes to `codex_python_sdk`. `claude:sdk` normalizes to `claude_python_sdk`.

The exact surface names remain the capability and telemetry boundary. Aliases are only accepted on input for `Harness` and `Session`; provider events, readiness results, runs, and capability profiles should continue to report exact surface names.

This keeps examples readable without hiding the important fact that the Codex CLI, Codex Python SDK, Codex app-server, Claude CLI, Claude Python SDK, and Claude TypeScript SDK have different feature sets.
