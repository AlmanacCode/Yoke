# Requests are event payloads

Yoke now has public `Request` and `Response` value objects.

The transport still belongs to each provider surface:

- Codex app-server receives JSON-RPC server requests while reading the turn
  stream.
- Claude Agent SDK receives approval and `AskUserQuestion` prompts through the
  live `can_use_tool` callback.

The shared model is only the payload shape. `Event` remains the stream item, and
request events now expose:

```python
event.request
event.response
```

This means a Codex app-server handler still receives the same `Event`, but can
inspect `event.request.kind`, `event.request.method`, and
`event.request.default`. The event also records the response Yoke sent back to
the provider.

This is the smallest useful abstraction. It avoids pretending Claude callbacks
and Codex JSON-RPC requests are the same runtime mechanism, while giving apps a
stable value shape for UI, logging, policies, and future callback wrappers.

Sources:

- https://code.claude.com/docs/en/agent-sdk/user-input
- https://code.claude.com/docs/en/agent-sdk/permissions
- https://developers.openai.com/codex/app-server

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_codex_app_events.py tests/test_codex_request_policy.py tests/test_capabilities.py
uv run ruff check src/yoke/models.py src/yoke/providers/codex_app/events.py src/yoke/__init__.py tests/test_codex_app_events.py
```

Observed:

```text
94 passed
All checks passed!
```
