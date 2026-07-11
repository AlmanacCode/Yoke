# 0092 - Claude options reach the SDK boundary

Re-read local references:

- `../eve/docs/agent-config.md`
- `../eve/docs/subagents.mdx`
- `../eve/docs/skills.mdx`
- `../openai-codex/codex-rs/app-server/README.md`
- `../openai-codex/sdk/python/README.md`
- `../claude-agent-sdk-python/README.md`
- `../claude-agent-sdk-python/examples/agents.py`
- `../claude-agent-sdk-python/examples/filesystem_agents.py`

Eve puts runtime configuration in `agent.ts`, but Yoke should not copy Eve's
runtime limits or workflow world until Yoke owns a durable runtime. For now,
provider-specific SDK knobs belong in provider options.

The concrete gap was Claude: `ProviderOptions.claude` existed, but the Claude
adapter did not pass it into `ClaudeAgentOptions`.

Yoke now types and forwards these Claude SDK options:

- `setting_sources`
- `include_partial_messages`
- `include_hook_events`
- `max_budget_usd`
- `raw`

Yoke-owned fields still win for the core contract: prompt, cwd, model, effort,
tools, agents, skills, output format, and task budget. `ClaudeOptions.raw` is
for extra Claude SDK kwargs Yoke has not typed yet, not for overriding the Yoke
model.
