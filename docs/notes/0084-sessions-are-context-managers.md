# Sessions are context managers

Yoke sessions are resource handles. Claude SDK sessions can own live subprocess clients, Codex app-server sessions own app-server processes, and Codex SDK sessions own SDK client/thread state.

`Session` now supports both async and sync context managers. `async with await harness.start() as session:` calls `await session.close()` on exit. `with session:` calls `session.close_sync()`.

This keeps provider cleanup behind the existing adapter `close(session)` port while making the public SDK harder to misuse. It also keeps sync/async parity: the same `Session` object supports async agent applications and small synchronous scripts.
