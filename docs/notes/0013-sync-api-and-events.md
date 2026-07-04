# Sync API and richer events

Yoke's core execution remains async because Claude SDK clients, app-server streams, and long-running provider sessions are naturally asynchronous. The public API now has explicit sync twins for script callers:

- `Harness.run_sync(...)`
- `Harness.start_sync(...)`
- `Harness.workflow_sync(...)`
- `Session.run_sync(...)`
- `Session.stream_sync(...)`
- `Session.close_sync()`

The sync methods call the async methods through `asyncio.run()` and fail clearly if called from inside an active event loop. This avoids a confusing method that sometimes returns a value and sometimes returns an awaitable.

The event model also gained small provider-neutral nouns:

- `ToolKind`
- `ToolStatus`
- `Tool`
- `Usage`

`Event` now carries optional structured tool metadata, token usage, provider session id, source thread id, source turn id, tool ids, tool input/result, and raw provider payload. This follows the CodeAlmanac rule of structured contracts before text scraping while avoiding CodeAlmanac-specific `Harness*` names in Yoke's public API.

Codex app-server now maps tool starts/results and token usage into these models. CodeAlmanac can later project Yoke events into its own richer job event schema without scraping raw JSON.
