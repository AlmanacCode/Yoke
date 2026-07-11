# Official entrypoint feature refresh

Date: 2026-07-04

Sources checked:

- Codex app-server: https://developers.openai.com/codex/app-server
- Codex SDK: https://developers.openai.com/codex/sdk
- Codex CLI reference: https://developers.openai.com/codex/cli/reference
- Codex subagents: https://developers.openai.com/codex/subagents
- Codex goals: https://developers.openai.com/codex/use-cases/follow-goals
- Claude TypeScript Agent SDK: https://code.claude.com/docs/en/agent-sdk/typescript
- Claude Python Agent SDK: https://code.claude.com/docs/en/agent-sdk/python
- Claude subagents: https://code.claude.com/docs/en/sub-agents
- Claude skills: https://code.claude.com/docs/en/skills
- Claude settings: https://code.claude.com/docs/en/settings

Current read:

Codex SDK is not a separate weak runtime. The official Python SDK controls the local Codex app-server over JSON-RPC and ships with a pinned Codex CLI runtime. That means a Yoke Codex SDK adapter should probably target app-server semantics instead of treating SDK and app-server as unrelated backends.

Codex app-server is the deep integration surface. It documents authentication, conversation history, approvals, and streamed agent events. Yoke should use this surface for rich sessions/events rather than trying to recover those concepts from plain `codex exec` output.

Codex CLI is still important because it exposes stable user workflows, config, `exec`, `resume`, `fork`, `app-server`, `mcp-server`, remote app-server connection flags, and goal/subagent user affordances. It should be modeled as its own surface, not as a generic subprocess escape hatch.

Codex subagents are documented as explicit parallel specialized agents. Activity is surfaced in the app and CLI. Yoke should continue treating Codex custom agents/subagents as provider-native when the selected surface documents them.

Codex goals are documented as a durable objective across turns with pause/resume/clear controls. Yoke should preserve the distinction between a goal option on a run and a provider-owned goal loop that can continue beyond one normal turn.

Claude Agent SDK has two major programmable shapes. TypeScript exposes rich options including programmatic agents, agent selection, in-process MCP tools, plugins, hook events, partial messages, abort control, session storage, and runtime flag settings. Python exposes `query()` and `ClaudeSDKClient` and passes operational environment settings to the CLI subprocess.

Claude subagents are independent-context workers with custom prompts, tool access, and permissions. Claude skills are folder-backed instruction/tool packages using `SKILL.md`, and Claude Code states those skills follow the Agent Skills open standard with Claude-specific extensions. This supports Yoke's folder-first `Skill` model.

Claude settings mention bundled skills and workflows as a settings-controlled surface. That reinforces that some Claude workflow behavior is not simply an SDK method; it can be part of the Claude Code runtime/tooling environment.

Design consequences:

- Keep `Surface` central.
- Keep `Status` evidence-rich.
- Treat `WorkflowRun.mode` as execution evidence, not provider identity.
- Treat Codex SDK as app-server-backed unless research proves a separate public runtime path.
- Keep CLI adapters useful, but do not promise streamed events or rich controls unless the CLI exposes them cleanly.
- Keep Claude skills/subagents/workflows as related but separate primitives because their discovery, execution, and configuration paths differ.
