# Claude background task messages map to Yoke timeline events

Date: 2026-07-04

Claude Python Agent SDK exposes background task messages separately from ordinary assistant content blocks. The docs define `TaskStartedMessage`, `TaskProgressMessage`, and `TaskNotificationMessage`; they cover backgrounded Bash commands, subagents spawned through the Agent tool, and remote agents.

Yoke now maps those task messages into the portable event stream:

- `TaskStartedMessage` -> `Event(kind="tool_use")` with started `Tool` metadata.
- `TaskProgressMessage` -> `Event(kind="tool_summary")` with task usage and last-tool display metadata.
- `TaskNotificationMessage` -> `Event(kind="tool_result")` with completion status, output file, summary, and final usage.

Task type mapping is intentionally small: `local_bash` becomes `ToolKind.SHELL`, while `local_agent` and `remote_agent` become `ToolKind.AGENT` plus `AgentCall(action="started")`. Unknown task types stay `ToolKind.UNKNOWN`.

This keeps subagent/background activity visible to embedders without making Yoke depend on Claude-specific task classes. CodeAlmanac can later map these events into its existing harness trace/timeline concepts.

Official docs checked:

- https://platform.claude.com/docs/en/agent-sdk/python

Next pressure test: Claude hooks expose `SubagentStart` and `SubagentStop` hook inputs with agent IDs and agent types. If Yoke users enable hook events, those may provide richer subagent identity than task messages alone.
