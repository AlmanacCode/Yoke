# Request policy belongs in folders

`RequestPolicy` is a Yoke value, not a live callback.

Yoke now exposes serializable policy fields:

```python
ClaudeOptions(policy=RequestPolicy.allow_tools("read"))
CodexAppServerOptions(policy=RequestPolicy.allow_tools("read"))
```

The older callback fields remain:

```python
ClaudeOptions(request_handler=callable)
CodexAppServerOptions(request_handler=callable)
```

Those callback fields are still runtime-only and excluded from folder saves.

This keeps the folder and SDK stories aligned. A simple policy can be committed
inside a Yoke folder; custom Python logic stays in code. Provider adapters use
the live callback first and fall back to the serializable policy.

This slice also makes option planning more honest:

- Claude policy implies `Feature.REQUEST_CALLBACKS`.
- Codex app-server policy implies `Feature.REQUEST_EVENTS`.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_folders.py tests/test_capabilities.py
uv run ruff check src/yoke/options.py src/yoke/providers/claude.py src/yoke/providers/codex_app_server.py tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_folders.py
```

## Observed verification

- `PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_folders.py tests/test_capabilities.py` passed: 135 tests.
- `uv run ruff check src/yoke/options.py src/yoke/providers/claude.py src/yoke/providers/codex_app_server.py tests/test_claude_options.py tests/test_codex_app_server_params.py tests/test_folders.py` passed.
- Follow-up fix: `runtime_options()` now walks Pydantic/Yoke models before checking `callable()`, because `RequestPolicy` is both serializable data and callable runtime behavior.
