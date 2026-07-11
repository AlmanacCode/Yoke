# Claude tool hooks carry subagent identity

Date: 2026-07-04

Claude Python Agent SDK docs say `PreToolUse`, `PostToolUse`, and `PostToolUseFailure` hook inputs include `agent_id` and `agent_type` when the hook fires inside a subagent. These hooks are observations around tool execution, not the tool execution stream itself, so Yoke keeps them as `Event(kind="hook")`.

Yoke now enriches those hook events with:

- `tool_id`, `tool_name`, and JSON `tool_input`.
- `Tool` metadata with started/completed/failed status.
- `tool_result` for `PostToolUse`.
- `tool_is_error` and error text for `PostToolUseFailure`.
- `AgentCall.agent_id`, `AgentCall.agent_type`, and action values `tool_starting`, `tool_completed`, or `tool_failed` when Claude provides subagent identity.

This completes the first pass over Claude's subagent event surfaces: inline tool blocks, background task messages, subagent start/stop hooks, and tool hooks inside subagents all map into the portable Yoke event language without exposing Claude SDK classes.

Official docs checked:

- https://platform.claude.com/docs/en/agent-sdk/python

Follow-up: an opt-in live Claude hook smoke now exists in `docs/notes/0134-claude-hook-live-smoke.md`.
