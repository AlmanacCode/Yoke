# Subagent status separates definitions from spawned-agent activity

Date: 2026-07-04

Yoke now exposes `status.subagents`.

The report has four support rows:

- `inline`: programmatic Yoke subagents on the selected surface.
- `declared`: named subagent definitions supplied to the provider.
- `filesystem`: provider-discovered custom agent files.
- `collab`: provider-native spawned-agent activity.

The report mode is:

- `provider_native`: the provider surface exposes native spawned-agent activity.
- `declared`: Yoke subagents map to provider-recognized agent definitions.
- `compiled`: Yoke subagents compile into instructions or artifacts.
- `unknown`: Yoke has incomplete metadata for the surface.
- `unsupported`: the surface has no known subagent support.

This distinction matters because Claude and Codex use similar words for different things.

Claude Python SDK subagents map to `AgentDefinition` values and can be invoked through the Agent tool. Claude subagents run in fresh isolated contexts, and the parent receives only the final summary. Claude also has filesystem subagents in `.claude/agents/`, automatic delegation by description, explicit invocation, resume semantics, and nested/background behaviors in the Claude Code product.

Codex CLI and Codex app expose subagent workflows when the user explicitly asks Codex to spawn agents. Codex handles spawning, routing follow-up instructions, waiting, and closing agent threads. Codex subagents inherit the current sandbox policy, and approval behavior depends on whether the run is interactive. Codex custom agents live as TOML files under `~/.codex/agents/` or `.codex/agents/`.

Codex app-server collab-agent events are not the same thing as Yoke's declared subagent map. Yoke observes provider-native app-server activity through `collabAgentToolCall` events and normalizes those into agent-call events. Yoke-declared subagents still compile into developer instructions on Codex app-server unless a later adapter deliberately maps them to a native provider primitive.

Sources checked:

- https://developers.openai.com/codex/subagents
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/agent-sdk/subagents
