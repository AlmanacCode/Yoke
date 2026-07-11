# Request events appear in status control

`Feature.REQUEST_EVENTS` now appears in `status.control`.

The public split is:

- `status.permissions`: static provider policy knobs such as sandbox,
  approval, network, tool rules, hooks, and callbacks
- `status.control`: live runtime controls such as login, model listing,
  interrupt, fork, request events, and experimental protocol support

This keeps the question readable for embedding apps:

```python
status = await harness.status()
print(status.control.request_events)
```

For the current surface matrix, `codex:app` reports `native` because Yoke can
surface Codex app-server server requests as normalized events and answer them
through `CodexAppServerOptions(request_handler=...)`.

Other Codex surfaces do not inherit this claim only because they are Codex. They
need their own documented interrupt-and-answer contract before Yoke marks
`request_events` as supported.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_readiness.py tests/test_capabilities.py
uv run ruff check src/yoke/status.py tests/test_readiness.py src/yoke/capabilities.py src/yoke/surfaces.py
```

Observed:

```text
103 passed
All checks passed!
```
