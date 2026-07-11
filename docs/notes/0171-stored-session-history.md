# Stored session history

Yoke now has stored session history APIs:

```python
page = await harness.sessions(limit=10)
history = await harness.read_session(page.sessions[0].id)
```

The neutral models are `SessionSummary`, `SessionList`, `SessionMessage`, and
`SessionHistory`. They carry provider ids, normalized display fields, and raw
provider payloads.

Provider wiring:

- Claude Python SDK: `list_sessions()`, `get_session_info()`, and
  `get_session_messages()`.
- Codex app-server: `thread/list` and `thread/read`.

This slice started as intentionally read-only. Yoke later added non-destructive
metadata controls: `Harness.rename_session()`, `Harness.tag_session()`,
`Session.rename()`, and `Session.tag()`. Archive, delete, and rollback remain
absent because they affect provider lifecycle state or stored history more
deeply and need a separate ownership design.

Capability matrix additions:

- `Feature.SESSION_LIST`
- `Feature.SESSION_READ`
- `Feature.SESSION_RESUME`
- `Feature.SESSION_RENAME`
- `Feature.SESSION_TAG`

This keeps the lifecycle boundaries precise. `SessionOptions(resume=...)` starts
or resumes a live provider session. `harness.read_session(...)` inspects stored
history without loading the thread or subscribing to events.

Sources:

- https://code.claude.com/docs/en/agent-sdk/python
- https://developers.openai.com/codex/app-server
