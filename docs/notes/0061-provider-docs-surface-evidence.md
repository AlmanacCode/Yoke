# Provider docs confirm surfaces are different products

Date: 2026-07-04

Sources checked:

- Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk/overview
- OpenAI Codex SDK docs: https://developers.openai.com/codex/sdk
- Codex app-server README: https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md

Findings:

- Claude documents the Agent SDK as Claude Code's agent loop and context management exposed through Python and TypeScript. The docs compare Agent SDK, Claude Code CLI, and Managed Agents as separate choices. That supports Yoke treating CLI, SDK, and managed/app surfaces as distinct profiles instead of one Claude provider bucket.
- Claude Agent SDK docs list sessions, streaming input, real-time responses, structured output, custom tools, MCP, subagents, skills, plugins, permissions, hooks, checkpointing, usage, and observability as SDK surfaces. Yoke should keep these primitives typed, but avoid assuming every one maps to Codex or every Claude entrypoint equally.
- OpenAI Codex SDK docs say the TypeScript SDK is more comprehensive than non-interactive mode, and the Python SDK controls local Codex app-server over JSON-RPC. That means Yoke's Python Codex SDK adapter and app-server adapter are close relatives, but not the same public surface.
- Codex app-server README describes JSON-RPC transports and three core primitives: thread, turn, and item. `turn/start` returns a turn, and clients stream notifications such as item start/completion, message deltas, tool progress, and `turn/completed` usage. This supports Yoke's decision to model app-server as the deepest event/session surface.

SDK consequence:

- `Profile` should remain `(provider, surface)` scoped.
- `Profile.runnable` should remain separate from conceptual support.
- `fits_for(...)` is useful because users need to see why the conceptual best surface may differ from the runnable best surface.
- `Harness.require(...)` should stay runnable by default because it creates a run-capable object.

This is not just taste. It is directly reflected in provider documentation: the same provider exposes different operational products with different lifecycle, event, and deployment semantics.
