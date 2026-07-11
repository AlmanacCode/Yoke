# Codex workflows can mean Agents SDK orchestration

Date: 2026-07-04

Sources checked:

- https://developers.openai.com/codex/guides/agents-sdk
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/app/features
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.claude.com/docs/en/agent-sdk/subagents

Codex does document multi-agent workflows, but the current public shape is Codex CLI exposed as an MCP server and orchestrated by the OpenAI Agents SDK. That is real and useful, but it is not the same primitive as a provider-native Codex app-server workflow DSL.

For Yoke this means there are at least three workflow families:

- `yoke_portable`: Yoke runs a dependency DAG over harness turns.
- `provider_native`: a provider runtime owns the workflow primitive, such as Claude TypeScript SDK's `Workflow` tool.
- external orchestration: another framework, such as OpenAI Agents SDK, coordinates Codex as one participant through MCP tools.

Yoke should not collapse external orchestration into `Feature.NATIVE_WORKFLOW`. It may deserve a later adapter or package integration, but the ownership is different: the Agents SDK owns handoffs, traces, guardrails, and orchestration, while Codex CLI is one MCP-backed worker.

This is another reason `WorkflowRun.mode` should be execution evidence rather than marketing vocabulary. A future integration can report a distinct mode if Yoke intentionally owns an Agents SDK bridge.
