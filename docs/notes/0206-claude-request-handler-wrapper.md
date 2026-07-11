# Claude request handler wrapper

Yoke now lets Claude use the same `Request` and `Response` payload language that
Codex app-server request events use.

The runtime mechanism is still Claude-native. `ClaudeOptions(request_handler=...)`
lowers to Claude Agent SDK `can_use_tool`. Direct `can_use_tool` still wins when
the caller supplies it.

The handler shape is:

```python
async def handler(event, default):
    return Response.allow()
```

Yoke builds an `Event` with `event.request` and `event.response`, calls the
handler, then converts the result to Claude SDK `PermissionResultAllow` or
`PermissionResultDeny`.

`AskUserQuestion` becomes `RequestKind.USER_INPUT`. Other Claude tool approval
callbacks become `RequestKind.APPROVAL`.

This is not a universal approval system. Codex app-server still uses JSON-RPC
request events. Claude still uses callback pauses. Yoke only shares the payload
shape so app UIs, logs, and policies can read a consistent model.

Sources:

- https://code.claude.com/docs/en/agent-sdk/user-input
- https://code.claude.com/docs/en/agent-sdk/permissions
- https://code.claude.com/docs/en/agent-sdk/python

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_capabilities.py
uv run ruff check src/yoke/models.py src/yoke/options.py src/yoke/providers/claude.py tests/test_claude_options.py
```

Observed:

```text
92 passed
All checks passed!
```
