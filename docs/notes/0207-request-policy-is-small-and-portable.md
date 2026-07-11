# Request policy is small and portable

Yoke now has a provider-neutral `RequestPolicy`.

It works with the shared request payload shape:

```python
policy = RequestPolicy.allow_tools("read", "search")
```

The policy returns a Yoke `Response`. Each provider adapter lowers that response
to its native mechanism:

- Claude lowers `Response.allow()` / `Response.deny()` to
  `PermissionResultAllow` / `PermissionResultDeny`.
- Codex app-server lowers `Response.allow()` / `Response.deny()` to JSON-RPC
  request results such as `{"decision": "accept"}` or
  `{"decision": "decline"}`.

`CodexRequestPolicy` remains separate. It is still the right tool for
Codex-specific choices such as `acceptForSession`, and it should not become the
portable policy surface.

This keeps the public API pleasant without erasing provider semantics.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_codex_request_policy.py tests/test_codex_app_events.py tests/test_claude_options.py
uv run ruff check src/yoke/policies.py src/yoke/providers/codex_app/events.py src/yoke/__init__.py tests/test_codex_request_policy.py tests/test_codex_app_events.py tests/test_claude_options.py
```

Observed:

```text
32 passed
All checks passed!
```
