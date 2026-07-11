# Claude subagent hooks preserve agent identity

Date: 2026-07-04

Claude Python Agent SDK hook inputs expose subagent identity that task messages do not fully carry. The docs list `SubagentStartHookInput` with `agent_id` and `agent_type`; `SubagentStopHookInput` adds `agent_transcript_path` and `stop_hook_active`.

Yoke now keeps ordinary `HookEventMessage` values as `Event(kind="hook")`, but enriches `SubagentStart` and `SubagentStop` hooks with provider-neutral agent metadata:

- `Event.agent.agent_id`
- `Event.agent.agent_type`
- `Event.agent.action` as `started` or `stopped`
- `Event.tool.kind = ToolKind.AGENT`
- `Event.tool.status = started` or `completed`
- `Event.tool.path` for the subagent transcript path on stop

This is an additive public model change: `AgentCall` now has `agent_id` and `agent_type`. That is cleaner than overloading Codex thread IDs with Claude identity fields.

Official docs checked:

- https://platform.claude.com/docs/en/agent-sdk/python

Follow-up: pre/post tool hook inputs with `agent_id` and `agent_type` are now covered in `docs/notes/0133-claude-tool-hooks-carry-subagent-identity.md`.
