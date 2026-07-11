# Constructor-level channel constraints

Date: 2026-07-04

## Change

`Harness` and `Session` now accept a persistent `channel` field.

```python
harness = Harness(
    provider="codex",
    channel=Channel.APP_SERVER,
    agent=agent,
    cwd=repo,
)

session = Session(provider="codex", channel="app_server", id="thread-1")
```

The persistent channel is used by `plan()`, `require()`, `run()`, `start()`, and session turns unless a method call passes a one-off `channel=` override.

## Semantics

- `surface` names the exact provider entrypoint.
- `channel` names the broad exposure path.
- If no surface is set, channel helps Yoke choose one.
- If a surface is set, channel validates that surface.
- A mismatch makes `plan().ok` false and makes `require(...)` raise.

## Why this belongs on the constructor

Most callers should not need to remember that every app-server-specific feature selection must pass `channel=Channel.APP_SERVER` manually. If they know the harness should be app-server-backed, that belongs on the harness.

This keeps Yoke readable:

```python
Harness(provider="codex", channel="app_server", agent=agent, cwd=repo)
```

is clearer than carrying `channel="app_server"` across every `plan`, `require`, `run`, or `start` call.

## Boundary

Do not treat constructor `channel` as a replacement for explicit features. It narrows the candidate set; `requires=[Feature.X]` or option-implied features still decide what the selected surface must support.
