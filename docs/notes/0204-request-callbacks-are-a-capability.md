# Request callbacks are a capability

Yoke now treats request callbacks as a first-class `Feature`.

`Feature.REQUEST_EVENTS` means a provider emits mid-run requests into the event
stream. Codex app-server has this shape, and Yoke answers requests through
`CodexAppServerOptions.request_handler`.

`Feature.REQUEST_CALLBACKS` means the embedding app supplies an SDK callback
that can pause provider execution. Claude Agent SDK has this shape through
`can_use_tool`, which receives both permission prompts and `AskUserQuestion`
clarifying questions.

This keeps planning honest:

```python
harness.plan(features=(Feature.REQUEST_CALLBACKS,))
```

selects Claude SDK, while Codex app-server still plans for
`Feature.REQUEST_EVENTS`.

Yoke infers `Feature.REQUEST_CALLBACKS` from `ClaudeOptions.can_use_tool` and
raw `can_use_tool` / `canUseTool` values. Static Claude permission fields still
infer `Feature.CLAUDE_PERMISSIONS`.

Sources:

- https://code.claude.com/docs/en/agent-sdk/user-input
- https://code.claude.com/docs/en/agent-sdk/permissions
- https://developers.openai.com/codex/app-server

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_readiness.py tests/test_claude_options.py
uv run ruff check src/yoke/capabilities.py src/yoke/surfaces.py src/yoke/status.py src/yoke/options.py tests/test_capabilities.py tests/test_readiness.py
```

Observed:

```text
116 passed
All checks passed!
```
