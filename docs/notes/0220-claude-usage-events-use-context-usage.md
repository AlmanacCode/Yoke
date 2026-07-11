# Claude usage events use the neutral context_usage kind

Claude SDK messages can carry token usage on assistant messages, result messages, and background task messages. Yoke's neutral event vocabulary already had `context_usage`, and Codex app-server uses it for `thread/tokenUsage/updated`.

Claude assistant/result usage previously emitted raw `kind="usage"`, which made downstream consumers branch on provider-specific event names for the same concept. Claude assistant/result usage now emits `EventKind.CONTEXT_USAGE` while keeping the same typed `Usage` payload and provider session/event ids.

Background task progress and task notification events still remain `tool_summary` / `tool_result` because their primary semantic event is task progress/completion; they carry `event.usage` as an attached payload.

Touched files:

- `src/yoke/providers/claude.py`
- `tests/test_claude_events.py`

Verification:

- `PYTHONPATH=src uv run pytest tests/test_claude_events.py tests/test_codex_app_events.py tests/test_results.py`
- `uv run ruff check src/yoke/providers/claude.py tests/test_claude_events.py`
