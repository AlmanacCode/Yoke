# 0043 - Codex custom agent files are a compile target

Codex custom agents are native project or user configuration files, not only
prompt text. Current Codex docs say project-scoped custom agents live under
`.codex/agents/*.toml`; each file defines one agent with `name`,
`description`, and `developer_instructions`, and can also carry session config
keys such as `model`, `model_reasoning_effort`, `sandbox_mode`,
`mcp_servers`, and `skills.config`.

Yoke now compiles direct `Agent.subagents` into `CodexAgentFile` values through
`yoke.providers.codex_agents.codex_agent_files()`. The compiler returns paths
and TOML bytes but does not write `.codex/agents` during a run. A caller or a
future explicit materializer owns filesystem mutation.

This keeps the public Yoke model provider-neutral while still respecting the
fact that Codex support depends on surface:

- Codex CLI and app can use `.codex/agents/*.toml` for native custom agents.
- Codex app-server remains the richest live/session surface for goals,
  streaming, model listing, plugins, skills, and thread metadata.
- Prompt compilation remains useful for surfaces where Yoke is not allowed to
  materialize project configuration.

Sources checked on 2026-07-04:

- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/app-server
