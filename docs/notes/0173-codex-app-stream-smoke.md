# Codex app-server stream smoke

Date: 2026-07-04

`scripts/smoke_harnesses.py` now includes `--run-codex-app-stream`.

The command exercises `Harness.stream_sync()` against the Codex app-server surface:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
```

The smoke verifies three things:

- Yoke receives the provider session event.
- Yoke receives a final `done` event.
- The streamed event messages include the expected text `yoke-stream-smoke`.

This is a live-provider check, not a unit test. It depends on local Codex authentication and may consume provider resources. It should stay in the manual smoke script rather than the normal test suite.

Live result on 2026-07-04:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server stream: events=15 kinds=provider_session,warning,tool_use,tool_result,tool_use,tool_result,tool_use,text_delta,text_delta,text_delta,text_delta,text_delta,text,context_usage,done contains_smoke=True
```

This proves the local Codex app-server adapter can stream normalized Yoke `Event` values through the public `Harness.stream_sync()` API in this environment.
