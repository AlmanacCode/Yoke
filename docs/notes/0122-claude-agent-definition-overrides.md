# Claude AgentDefinition overrides

Yoke now exposes `ClaudeAgentOptions` for provider-specific Claude subagent fields.

The neutral `Agent` model stays small: instructions, description, model, tools, skills, subagents, workflows, goal, and generic permissions. Claude-specific `AgentDefinition` fields now live under `ProviderOptions(claude=ClaudeOptions(agents={...}))`.

Modeled fields include:

- `tools`
- `disallowed_tools` / `disallowedTools`
- `model`
- `skills`
- `memory`
- `mcp_servers` / `mcpServers`
- `initial_prompt` / `initialPrompt`
- `max_turns` / `maxTurns`
- `background`
- `effort`
- `permission_mode` / `permissionMode`
- `raw`

The adapter merges these overrides into the generated Claude SDK `AgentDefinition` for a matching Yoke subagent name. Core `description` and `prompt` still come from the Yoke subagent itself, so the provider override is for Claude execution metadata rather than replacing the declared subagent identity.

This follows the current Claude docs: Claude subagents are SDK-native and have richer fields than Yoke's provider-neutral agent model should carry.
