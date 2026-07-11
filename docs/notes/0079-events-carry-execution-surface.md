# Events carry execution surface

Yoke events now carry optional `surface`, matching `Run.surface` and `Session.surface`.

Streaming is surface-specific. Codex CLI JSONL events, Codex app-server JSON-RPC notifications, Codex Python SDK stream events, and Claude SDK messages are different contracts. A normalized event should keep enough evidence for callers to know which contract produced it.

Built-in adapters stamp event surfaces at adapter boundaries instead of pushing surface into every low-level parser. This keeps parsing functions focused on provider message shape while making the public event stream self-describing.

This matters for CodeAlmanac integration later: job logs can persist `provider + surface + event kind` without inferring the execution path from surrounding run state.
