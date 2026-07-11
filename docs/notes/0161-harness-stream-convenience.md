# 0161 - Harness stream convenience

## Context

Current provider docs keep reinforcing that streaming is a session-shaped capability, even when the user only wants one streamed turn.

Claude Python SDK separates `query()` from `ClaudeSDKClient`. `query()` creates a fresh session for each interaction and yields messages as they arrive, while `ClaudeSDKClient` keeps a continuous conversation and supports session control such as interrupts.

Codex app-server exposes lower-level thread and turn APIs. A client starts or resumes a thread, starts a turn, and reads `thread/*`, `turn/*`, `item/*`, and server-request notifications from the transport stream. Goals live on Codex threads, not on an isolated one-shot process.

## Yoke change

Yoke now exposes:

```python
async for event in harness.stream("Make the change."):
    print(event.kind, event.message)

for event in harness.stream_sync("Make the change."):
    print(event.kind, event.message)
```

`Harness.stream(...)` selects a surface that supports streaming, starts a short-lived session, streams one turn through `Session.stream(...)`, and closes the session in a `finally` block.

This keeps the public API small without lying about the provider model. Streaming still flows through session-capable adapters; the harness method is only a convenience for the common one-turn case.

## Why this shape

- `run(...)` is the collect-the-answer convenience.
- `stream(...)` is the stream-one-turn convenience.
- `session()` / `start()` remain the explicit multi-turn lifecycle APIs.

That mirrors provider reality. Claude `query()` is the quick one-off path and `ClaudeSDKClient` is the long-lived path. Codex app-server always has thread/turn machinery underneath, but Yoke can own the short-lived lifecycle for callers.

## Test pressure

The test adapter now declares `Feature.GOAL` because the test uses goal-bearing run options. That is intentional: runtime planning must be driven by declared capabilities, even for fakes. This catches adapter contracts that accidentally accept options they did not claim to support.

## Sources checked

- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/workflows
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/subagents

## Verification

- `PYTHONPATH=src uv run pytest tests/test_sessions.py` -> 11 passed.
- `uv run ruff check src/yoke/models.py tests/test_sessions.py` -> passed.
