# Request events versus request callbacks

Yoke now reports two different mid-run interaction shapes:

- `status.control.request_events`: provider requests arrive as normalized Yoke
  events and can be answered through the provider event/request loop
- `status.control.request_callbacks`: provider requests arrive through an SDK
  callback supplied by the embedding application

This distinction matters for Claude and Codex.

Codex app-server uses request events. It sends JSON-RPC server requests for
tool approvals, user input, and other app-server interaction points. Yoke maps
those into events such as `approval_request`, `user_input_request`, and
`tool_request`, then answers through `CodexAppServerOptions.request_handler`.

Claude Agent SDK uses request callbacks. Claude docs say tool approvals and
`AskUserQuestion` clarifying prompts both trigger the `can_use_tool` callback.
That callback can remain pending while the SDK waits, and it can return the
user's approval, denial, or answer. This is runtime SDK code, not a normal Yoke
event stream.

Current status shape:

```text
codex:app      request_events=native       request_callbacks=unsupported
claude:sdk     request_events=unsupported  request_callbacks=native
```

Yoke already forwards Claude `can_use_tool` through `ClaudeOptions`, and those
callbacks are marked runtime-only so they do not silently serialize into Yoke
folders.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_readiness.py tests/test_capabilities.py tests/test_claude_options.py
uv run ruff check src/yoke/status.py tests/test_readiness.py
```

Observed:

```text
114 passed
All checks passed!
```

Sources:

- https://code.claude.com/docs/en/agent-sdk/user-input
- https://code.claude.com/docs/en/agent-sdk/permissions
- https://developers.openai.com/codex/app-server
