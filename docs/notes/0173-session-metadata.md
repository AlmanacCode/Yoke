# 0173 - Session metadata is normalized cautiously

Yoke now exposes non-destructive session metadata controls:

```python
await harness.rename_session(session_id, "Bug bash")
await harness.tag_session(session_id, "needs-review")
await session.rename("Bug bash")
await session.tag(None)
```

Claude Python SDK lowers rename and tag to `rename_session()` and `tag_session()`.

Codex app-server lowers rename to `thread/name/set`. Codex app-server does not expose a portable session tag operation, so `SESSION_TAG` is unsupported on that surface.

Yoke still does not expose archive, delete, or rollback. Those are lifecycle or history-mutating operations and need a separate design pass before they become public API.
