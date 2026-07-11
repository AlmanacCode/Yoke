# Claude tool blocks map to Yoke tool events

Date: 2026-07-04

The Claude Python Agent SDK documents `AssistantMessage.content` as a list of content blocks and includes `ToolUseBlock` and `ToolResultBlock` in the block union. Yoke should use those typed blocks directly instead of scraping tool activity out of text.

Yoke now maps Claude `ToolUseBlock` to `Event(kind="tool_use")` with `tool_id`, `tool_name`, JSON `tool_input`, and `Tool` display metadata. Obvious Claude tool names map to portable `ToolKind` values: `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `WebFetch`, `WebSearch`, `Agent`, `Task`, and `mcp__*`.

Yoke now maps Claude `ToolResultBlock` to `Event(kind="tool_result")` with `tool_id`, `tool_result`, `tool_is_error`, and completed/failed `ToolStatus`.

This keeps Yoke provider-neutral without dropping provider-native shape. CodeAlmanac or another embedder can render timeline/tool activity from Yoke events without knowing the Claude SDK block classes.

Official docs checked:

- https://platform.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/skills

Follow-up: Claude background task messages (`TaskStartedMessage`, `TaskProgressMessage`, `TaskNotificationMessage`) are now covered in `docs/notes/0131-claude-background-task-events.md`.
