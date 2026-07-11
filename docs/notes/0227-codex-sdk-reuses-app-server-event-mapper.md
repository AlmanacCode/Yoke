# Codex SDK reuses the app-server event mapper

2026-07-04

Codex Python SDK streamed notifications now pass through Yoke's Codex app-server event mapper when possible.

The SDK exposes the same app-server event taxonomy as typed Python notification objects, so maintaining a separate SDK event taxonomy inside Yoke would duplicate provider logic and drift from the app-server surface. `sdk_events(...)` converts typed SDK notifications into the JSON-like app-server notification shape, calls the shared mapper, and then restores the original SDK object as `event.raw`.

This means SDK streams now receive the same normalized event kinds as app-server streams for supported notification methods, including text deltas and account rate-limit updates. Unknown SDK notifications still become `EventKind.STREAM_EVENT` with the provider method in `event.message`.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_codex_python_sdk.py tests/test_codex_app_events.py tests/test_events.py`
- `PYTHONPATH=src uv run ruff check src/yoke/providers/codex_sdk.py tests/test_codex_python_sdk.py`
