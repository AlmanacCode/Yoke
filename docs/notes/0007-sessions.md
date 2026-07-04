# 0007: Sessions are runtime handles

Slice date: 2026-07-03

## Pressure

The old `Session` model was only `{provider, id, goal}`. That was too weak.

Claude Python SDK sessions need a live `ClaudeSDKClient` connected inside one
async runtime. The client owns a subprocess, message stream, interrupts, MCP
status, context usage, model changes, and disconnect behavior.

Codex CLI sessions are different. `codex exec --json` creates a persisted
thread id, and `codex exec resume <id> --json` sends the next turn. There is no
long-lived Python object unless Yoke creates one.

## Decision

`Session` is now the user-facing runtime handle with:

- `await session.run("...")`
- `async for event in session.stream("...")`
- `await session.close()`

The adapter still owns provider mechanics:

- Claude adapter keeps live `ClaudeSDKClient` instances in adapter state keyed
  by Yoke session id.
- Codex CLI adapter stores enough context on the session handle to resume the
  CLI thread by id.

This keeps the public model simple while preserving provider reality.

## Tradeoff

`Session` now carries optional `agent`, `cwd`, and `permissions`. That is not as
pure as a tiny serializable handle, but it makes Codex CLI resume usable without
global hidden state. If this starts to feel heavy, split `Handle` from
`Session` later.

## Surface note

This slice implements:

- Claude Python SDK live sessions.
- Codex CLI resumable sessions.

It does not implement Codex app-server sessions. App-server still needs a
separate surface adapter because it owns richer thread lifecycle and mutable
goals.

## Discord update gap

The goal asks for Discord updates via Relayforge. Running:

```bash
relayforge status --config relay.config.json
```

failed in the Yoke repo because `relay.config.json` does not exist. Future
slice updates can be sent after Relayforge is configured for this repo or this
thread is connected to a channel.

## Real smokes

Claude live session:

```bash
uv run --with claude-agent-sdk --with pydantic --with pyyaml python examples/claude_session.py
```

Result:

```text
first
yoke
```

The first Codex session smoke failed because the bridge placed CLI options
after the `resume` subcommand:

```text
error: unexpected argument '--sandbox' found
```

That confirmed another surface detail: for `codex exec resume`, Yoke must emit
global `codex exec` options before appending `resume <id> -`.

After fixing argument order, Codex CLI resume passed:

```bash
uv run --with pydantic --with pyyaml python examples/codex_session.py
```

Result:

```text
first
yoke
```
