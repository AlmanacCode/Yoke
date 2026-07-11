# Claude thinking and server tool blocks

2026-07-04

Yoke now maps additional Claude assistant content blocks into the neutral event stream.

Claude Agent SDK parses `ThinkingBlock`, `ServerToolUseBlock`, and `ServerToolResultBlock` alongside normal text/tool blocks. Before this slice, Yoke ignored those block types inside `AssistantMessage`.

Mapping:

- `ThinkingBlock` becomes `EventKind.TOOL_SUMMARY` with `message="thinking"`
- Yoke does not copy the thinking text into `event.message`; it records `has_thinking` and the provider signature in `tool_result`, while preserving the original SDK message in `raw`
- `ServerToolUseBlock` maps through the normal `tool_use` event path
- `ServerToolResultBlock` maps through the normal `tool_result` event path
- Claude server tool names such as `web_search` now infer `ToolKind.WEB`

The reasoning boundary is intentional: provider-emitted thinking is visible to low-level embedders through `raw`, but the normalized event stream does not accidentally render it like assistant text.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_claude_events.py`
- `PYTHONPATH=src uv run ruff check src/yoke/providers/claude.py tests/test_claude_events.py`
