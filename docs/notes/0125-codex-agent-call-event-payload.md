# Codex agent-call event payloads

2026-07-04

Codex app-server collaboration-agent activity is provider-native event activity, not Yoke-declared subagents.

Yoke already maps Codex `collabAgentToolCall` items to `ToolKind.AGENT`. This slice adds a typed `AgentCall` payload on `Event.agent` so embedding apps do not have to parse `tool_result` to find child-thread metadata.

The payload currently carries:

- `action`
- `sender_thread_id`
- `receiver_thread_ids`
- `new_thread_id`
- `prompt`
- `model`
- `reasoning_effort`
- `states`

`tool_result` remains populated with the previous raw-compatible mapping. This keeps existing callers working while giving UI and orchestration layers a clean typed path.

This should stay separate from `Agent.subagents`. Claude SDK `AgentDefinition` subagents are client-declared workers. Codex app-server collab-agent events are provider-emitted lifecycle/tool activity.
