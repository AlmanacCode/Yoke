# Claude SDK entrypoint map

Checked against the current Claude Code docs on 2026-07-04:

- Python SDK reference: <https://code.claude.com/docs/en/agent-sdk/python>
- TypeScript SDK reference: <https://code.claude.com/docs/en/agent-sdk/typescript>
- Subagents guide: <https://code.claude.com/docs/en/sub-agents>
- Skills guide: <https://code.claude.com/docs/en/skills>

Claude has real entrypoint differences.

The Python SDK exposes two usage modes:

- `query()` for one-off runs.
- `ClaudeSDKClient` for a live multi-exchange session.

The Python reference says `query()` creates a new session by default, while `ClaudeSDKClient` reuses the same session. It also marks interrupts as available on `ClaudeSDKClient` and not on `query()`.

The Python SDK `ClaudeAgentOptions` includes:

- `agents`
- `plugins`
- `skills`
- `hooks`
- `include_partial_messages`
- `include_hook_events`
- `resume`
- `continue_conversation`
- `max_turns`
- `max_budget_usd`
- `output_format`
- `permission_mode`
- `can_use_tool`
- `sandbox`
- `session_store`

The Python SDK has programmatic subagents through `AgentDefinition`. Important fields include:

- `description`
- `prompt`
- `tools`
- `disallowedTools`
- `model`
- `skills`
- `memory`
- `mcpServers`
- `initialPrompt`
- `maxTurns`
- `background`
- `effort`
- `permissionMode`

The Python docs explicitly warn that `AgentDefinition` uses camelCase field names, even though top-level `ClaudeAgentOptions` uses snake_case. Yoke already follows this in the Claude adapter.

Claude skills are native when Claude can discover them through settings or plugins. The SDK option `plugins` loads local plugin paths, and `skills` chooses which discovered skill names are available or preloaded. That is not the same as Yoke automatically making an arbitrary `agent/skills/foo/SKILL.md` folder native.

Current Yoke behavior:

- Claude Python SDK: Yoke compiles folder and inline skill text into the system prompt, and passes skill names through the SDK options.
- Codex app-server: Yoke wires packaged `skills/*/SKILL.md` folders as native extra roots and compiles inline skills.
- Codex CLI: Yoke compiles skills into prompt text.

This is the right conservative boundary until Yoke gains an explicit Claude plugin writer/loader. At that point, packaged Yoke skills can become native for Claude too.

Workflow finding:

The TypeScript SDK reference currently mentions a `Workflow` tool being available in Agent SDK v0.3.149 and later. The Python reference checked here does not expose the same named workflow type in the option fields above. So Yoke should not make core workflow execution depend on Claude's TypeScript-only workflow tool.

Yoke's workflow abstraction should remain provider-neutral orchestration for now:

- Native if a provider entrypoint exposes a stable workflow primitive.
- Emulated by Yoke when the provider only exposes sessions/runs.
- Compiled into prompt only for very simple "follow these steps" hints.

This keeps Claude TypeScript workflow support as an optional adapter strength, not the foundation of the Yoke model.

