# Harness session is the clean context API

`Session` is a context manager, but `async with await harness.start() as session:` is visually awkward. Yoke now exposes `Harness.session()` for async code and `Harness.session_sync()` for synchronous code.

`Harness.session(options)` returns a small context manager that calls `await harness.start(options)` on entry and `await session.close()` on exit. `Harness.session_sync(options)` does the same with `start_sync()` and `close_sync()`.

`start()` remains the explicit lower-level API for callers that need to store, return, or manage the session handle manually. `session()` is the safer default for examples and applications that want scoped lifecycle ownership.

This preserves the existing adapter port shape: providers still implement `start(...)` and `close(session)`. The context helper is SDK ergonomics, not a new provider abstraction.
