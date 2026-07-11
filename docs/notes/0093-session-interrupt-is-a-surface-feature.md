# 0093 - Session interrupt is a surface feature

Re-read local provider docs:

- `../claude-agent-sdk-python/src/claude_agent_sdk/client.py`
- `../openai-codex/codex-rs/app-server/README.md`

Claude's live `ClaudeSDKClient` exposes `interrupt()`. Codex app-server exposes
`turn/interrupt` for an active turn. Codex CLI resume sessions do not expose a
live turn handle that Yoke can interrupt.

Yoke now models this as `Feature.INTERRUPT` and exposes:

```python
await session.interrupt()
session.interrupt_sync()
```

Support is surface-specific:

- Claude Python SDK: native
- Codex app-server: native
- Codex CLI: unsupported
- Codex Python SDK and TypeScript SDK: unknown until verified against their turn
  handles

The app-server adapter stores the active turn id on its live thread object and
sends `turn/interrupt` with `{ threadId, turnId }`. The public `Session` stays a
simple handle; the adapter owns provider control-plane state.

Follow-up: app-server `turn/completed` can report `status: "interrupted"`.
Mapping that provider status into `RunStatus.CANCELLED` should be a separate
result-semantics slice rather than being hidden inside the interrupt method.
