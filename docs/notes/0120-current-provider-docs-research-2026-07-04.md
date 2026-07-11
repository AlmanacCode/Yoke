# Current provider docs research on 2026-07-04

Read current public docs for Claude Agent SDK and Codex surfaces.

Sources:

- Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk/overview
- Claude Agent SDK subagents: https://code.claude.com/docs/en/agent-sdk/subagents
- Claude Agent SDK skills: https://code.claude.com/docs/en/agent-sdk/skills
- Claude Agent SDK sessions: https://code.claude.com/docs/en/agent-sdk/sessions
- Claude Agent SDK Python reference: https://code.claude.com/docs/en/agent-sdk/python
- Codex subagents: https://developers.openai.com/codex/subagents
- Codex SDK: https://developers.openai.com/codex/sdk
- Codex app-server README: https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md

## Claude implications

Claude Agent SDK is explicitly positioned as Claude Code's agent loop as a Python/TypeScript library. The overview says it gives applications the same tools, agent loop, and context management that power Claude Code.

Subagents are an SDK-level option. The docs recommend programmatic subagents through the `agents` parameter in query options, while also supporting filesystem subagents in `.claude/agents/`. Programmatic agents take precedence over filesystem agents with the same name.

Claude `AgentDefinition` carries more than prompt text. It includes description, prompt, tools, disallowed tools, model, skills, memory, MCP servers, initial prompt, max turns, background behavior, effort, and permission mode. Yoke should keep its own `Agent` model small, but the Claude adapter needs room to pass through Claude-specific fields.

Claude subagents are context-isolated. A subagent starts with a fresh conversation and receives the parent-to-subagent prompt, its own system prompt, tool definitions, and selected project/skill context. It does not inherit the parent conversation history or tool results. Yoke workflow/subagent design should preserve this mental model rather than pretending subagents are just function calls.

Claude subagents can be automatic or explicit. Claude chooses based on the subagent `description`, but prompts can request a named subagent. Current docs also describe dynamic agent creation at query time.

Claude subagent lifecycle is richer than Yoke currently models. Docs mention background default behavior in newer Claude Code versions, nested subagents with depth limits, detection through Agent tool events, and resume by carrying both the session ID and an agent ID. Yoke should avoid claiming full native subagent lifecycle support until it exposes these details or keeps them in provider-specific raw/event data.

## Codex implications

Codex public subagent docs describe subagent workflows as something Codex orchestrates when explicitly asked. Codex can spawn specialized agents in parallel, wait for results, and return a consolidated response. Subagent activity is surfaced in the Codex app and CLI; IDE visibility is documented as coming later.

Codex subagents are not the same as Claude SDK `agents={...}`. The Codex docs emphasize explicit prompting and Codex-owned orchestration. Yoke should continue distinguishing `COLLAB_AGENT_TOOLS` and user-declared/compiled subagents rather than treating Codex subagents as the same native API shape as Claude `AgentDefinition`.

Codex SDK docs say the Python SDK controls the local Codex app-server over JSON-RPC and includes a pinned Codex CLI runtime. That supports Yoke's current surface model: `codex_python_sdk` is a distinct surface, but it is conceptually close to app-server rather than a generic remote API.

Codex SDK exposes sync and async entrypoints, thread start/resume, repeated `run(...)` on a thread, and sandbox presets. Yoke's sync/async pair and session-first API are aligned with this surface.

Codex app-server docs add lower-level client concerns: initialize must happen once per transport, clients should send `clientInfo`, initialization can advertise capabilities such as `experimentalApi`, notification opt-outs, and OpenAI form elicitation support. Yoke already models `experimentalApi`; future Codex app-server options should probably add typed support for notification opt-outs and MCP form elicitation instead of leaving them only in `raw`.

## Yoke design pressure

The provider-neutral noun `Agent` is still good, but subagent execution cannot be a single provider-neutral promise.

Claude has a native SDK-level subagent map with rich `AgentDefinition` options. Codex has visible app/CLI subagent workflows plus app-server collaboration events/tools, and custom agents map more naturally through filesystem agents or compiled instructions today.

Yoke should keep three layers separate:

- declared Yoke subagents in the folder/SDK model
- provider-native subagent mechanisms when the surface exposes them
- event/reporting surfaces that reveal provider-owned subagent activity

The next likely API work is provider-specific option depth, especially Claude `AgentDefinition` fields and Codex app-server initialization capabilities.
