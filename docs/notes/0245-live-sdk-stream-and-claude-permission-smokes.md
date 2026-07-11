# 0245 - Live SDK stream and Claude permission smokes

Date: 2026-07-04

This slice added and ran two new opt-in live smokes.

## Codex Python SDK stream

Command:

```bash
PYTHONPATH=src uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk-stream
```

Result: passed.

Observed behavior:

- Readiness found `openai_codex` version `0.1.0b2`.
- The live stream emitted 25 provider events.
- The SDK stream ended with `turn/completed`.
- The SDK stream did not expose final assistant text in Yoke `Event.message`; the smoke now validates streamed transport plus completion for this surface instead of app-server-style `provider_session` plus `done` plus text.

Decision:

- Codex app-server stream smoke keeps the stricter output-text check.
- Codex Python SDK stream smoke checks the real SDK event contract until the SDK exposes loaded final items or Yoke adds a separate final-result fetch.

## Claude Python SDK permission callback

Command:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-permissions
```

Result: passed.

Observed behavior:

- Claude auth was available via `claude.ai`.
- `ClaudeOptions(can_use_tool=...)` requires an AsyncIterable prompt. A plain string fails with `can_use_tool callback requires streaming mode`.
- A one-item AsyncIterable prompt can still close the control protocol too early in this SDK version.
- Adding a harmless `PreToolUse` hook keeps the control channel open long enough for the permission callback.
- Direct Claude SDK `can_use_tool` callbacks must return `PermissionResultAllow` or `PermissionResultDeny`; a plain dict is rejected.

Yoke change:

- `src/yoke/providers/claude.py` now converts prompts to the SDK AsyncIterable shape when Claude options include `can_use_tool`.
- `scripts/smoke_harnesses.py --run-claude-permissions` uses a temp file marker, a native `PermissionResultAllow`, and a harmless hook to exercise the live permission path.

## Verified

Focused tests and ruff passed:

```bash
PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_smoke_harnesses.py
PYTHONPATH=src uv run ruff check src/yoke/providers/claude.py scripts/smoke_harnesses.py tests/test_claude_options.py tests/test_smoke_harnesses.py
```

Result: 47 passed; ruff all checks passed.
