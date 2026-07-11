# Claude result pressure events

2026-07-04

Yoke now maps Claude `ResultMessage` pressure fields into the provider-neutral event stream.

Claude SDK result messages can carry more than final text, usage, and `done`. They can include provider errors, permission denials, and deferred tool use. These are not separate turns, but they are important for embedders that want a faithful UI or need to decide whether a run really completed cleanly.

Mapping:

- `errors` or `api_error_status` becomes `EventKind.ERROR`
- `permission_denials` becomes `EventKind.WARNING`
- `deferred_tool_use` becomes `EventKind.TOOL_REQUEST`
- the final `done` event still emits after these pressure events
- the original SDK result message is preserved in `event.raw`

This keeps `Run.status` separate from stream visibility. The provider adapter can still decide overall run success/failure, while the event stream exposes the pressure that occurred inside the provider result.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_claude_events.py`
- `PYTHONPATH=src uv run ruff check src/yoke/providers/claude.py tests/test_claude_events.py`
