# Claude task_updated events

2026-07-04

Yoke now maps Claude SDK `TaskUpdatedMessage` into the provider-neutral event stream.

Claude's SDK documents that terminal background task state can arrive only as `TaskUpdatedMessage`, without a matching `TaskNotificationMessage`. This matters for embedders that track active subagents or background tasks: ignoring `task_updated` can leave a task looking active after it has completed, failed, or been killed.

Mapping:

- non-terminal status such as `pending`, `running`, or `paused` becomes `EventKind.TOOL_SUMMARY`
- terminal status such as `completed`, `failed`, `stopped`, or `killed` becomes `EventKind.TOOL_RESULT`
- `killed` maps to `ToolStatus.DECLINED`, matching the SDK note that `task_notification` reports the same condition as `stopped`
- the patch is preserved in `event.tool_result`
- the original SDK message is preserved in `event.raw`

Verification:

- `PYTHONPATH=src uv run pytest tests/test_claude_events.py`
- `PYTHONPATH=src uv run ruff check src/yoke/providers/claude.py tests/test_claude_events.py`
