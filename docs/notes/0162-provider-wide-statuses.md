# 0162 - Provider-wide statuses

## Context

The hard part of Yoke is not asking whether a provider exists. It is asking which provider exposure path is ready and which features that path actually supports.

Codex is the clearest example. CLI, Python SDK, and app-server are all Codex, but they differ in streaming, goals, thread control, request handling, and app integration. Claude has the same pressure between `query()`, `ClaudeSDKClient`, CLI behavior, and dynamic workflows.

## Yoke change

`Harness.status()` remains the selected-surface API:

```python
status = await harness.status()
```

`Harness.statuses()` now checks every matching known surface for the harness provider:

```python
for status in await harness.statuses(channel=Channel.APP_SERVER):
    print(status.surface, status.available, status.supports(Feature.READABLE_GOAL))
```

`Harness.statuses_sync()` is the synchronous twin.

## Design rule

- `status()` answers: is this exact harness surface ready, and what does it claim to support?
- `statuses()` answers: across this provider family, which known surfaces match my channel filter, and what is each live readiness plus capability report?

This keeps surface choice visible for embedding apps like CodeAlmanac. A UI or lifecycle service can show that `codex_cli` is installed but lacks native thread goals, while `codex_app_server` is the richer app-server path.

## Verification

- `PYTHONPATH=src uv run pytest tests/test_readiness.py` -> 5 passed.
- `uv run ruff check src/yoke/models.py tests/test_readiness.py` -> passed.
