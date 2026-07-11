# 0044 - Entrypoints are not providers

The same provider exposes different functionality through different entrypoints.
Yoke should keep modeling `provider` and `surface` separately.

Codex has at least these documented entrypoints:

- CLI and TUI slash commands. `/goal` is an interactive command that attaches a
  persistent objective to the active thread. `/skills`, `/plan`, `/permissions`,
  `/agent`, and side conversations are also CLI/app concepts.
- Codex SDKs. The TypeScript SDK is documented as more comprehensive and
  flexible than non-interactive mode. The Python SDK is documented as
  `openai-codex`; it supports sync and async clients, thread creation, runs,
  sandbox presets, and local runtime pinning.
- App-server protocol. This is the rich client protocol for authentication,
  conversation history, approvals, streamed events, thread goals, model lists,
  skills, plugins, MCP, and collaboration-agent tool events.
- Custom agent files. Codex can load `.codex/agents/*.toml` files with `name`,
  `description`, `developer_instructions`, and optional config such as model,
  reasoning effort, sandbox, MCP servers, and skills.

Claude has at least these documented entrypoints:

- Claude Agent SDK. The Python and TypeScript SDKs expose the Claude Code agent
  loop as a library. The Python SDK has `query()` for one-shot runs and
  `ClaudeSDKClient` for interactive sessions.
- Claude SDK subagents. SDK subagents are usually programmatic
  `AgentDefinition` values. They isolate context, can run in parallel, can be
  explicitly invoked, and persist subagent transcripts independently.
- Claude filesystem extension surfaces. Skills are filesystem artifacts under
  `.claude/skills/<name>/SKILL.md`; the SDK does not register skills directly as
  in-memory objects. Plugins can package skills, agents, hooks, and MCP servers
  and are loaded by path.
- Claude hooks. The SDK supports both filesystem hooks from settings and
  programmatic hooks passed to `query()`.

Yoke implication:

- `Surface` should include documented entrypoints even before each one has a
  built-in adapter.
- Capability checks should always be per surface, never just per provider.
- A Yoke feature can compile to a provider artifact (`.codex/agents/*.toml`,
  Claude local plugin) without being active in a run until the caller chooses to
  materialize or load that artifact.
- Goals are especially surface-sensitive. Codex app-server has native
  `thread/goal/*` methods; Codex CLI exposes `/goal` interactively; Claude
  currently gets Yoke goals as prompt/task-budget context rather than readable
  mutable provider state.

Sources checked on 2026-07-04:

- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/cli/slash-commands
- https://developers.openai.com/codex/subagents
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/agent-sdk/plugins
- https://code.claude.com/docs/en/agent-sdk/claude-code-features
