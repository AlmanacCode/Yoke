# Request events are not permissions

Yoke now distinguishes permission configuration from provider request events.

`Feature.PERMISSIONS` means a caller can configure the provider's sandbox,
approval posture, network access, or tool rules.

`Feature.REQUEST_EVENTS` means the selected surface can interrupt a live turn
with a request that Yoke can surface and answer. In the current implementation
this is native only for `codex:app`.

For `codex:app`, server requests are normalized as:

- `approval_request`
- `user_input_request`
- `tool_request`
- later `request_resolved` notifications when the provider reports resolution

Callers answer those requests through:

```python
RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            app_server=CodexAppServerOptions(request_handler=handler)
        )
    )
)
```

This feature stays surface-specific. Codex CLI can accept permission flags and
Codex Python SDK can run turns, but Yoke should not claim they support request
events until their public entrypoints expose an equivalent interrupt-and-answer
contract.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_codex_app_events.py
uv run ruff check src/yoke/capabilities.py src/yoke/surfaces.py scripts/smoke_harnesses.py tests/test_capabilities.py
```

Observed:

```text
85 passed
All checks passed!
```
