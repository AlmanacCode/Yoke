# Codex app-server request smoke hardening

Codex app-server request handling is an entrypoint-specific Yoke feature. It
should not be treated as generic Codex support.

This slice hardened `scripts/smoke_harnesses.py --run-codex-app-request`.

The smoke now:

- deletes `.yoke-request-smoke.tmp` before the run starts
- asks Codex app-server to attempt a write under read-only permissions with
  approval set to `ask`
- records the normalized request event through
  `CodexAppServerOptions(request_handler=...)`
- accepts the default noninteractive response from Yoke
- removes the temp file if a future provider behavior creates it
- fails if the file was created unexpectedly

Live evidence from 2026-07-04:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-request
```

Observed:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server request: succeeded: requests=1 handler_calls=1 output='yoke-codex-request-smoke'
codex_app_server request: request-smoke-file-absent
```

Focused verification:

```bash
PYTHONPATH=src uv run pytest tests/test_codex_app_events.py
uv run ruff check scripts/smoke_harnesses.py
```

Observed:

```text
8 passed
All checks passed!
```

Design implication: request and approval events belong in Yoke's portable event
model, but the live support claim should stay attached to `codex:app` until
other Codex entrypoints expose equivalent request semantics.
