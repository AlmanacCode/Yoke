# Provider surfaces are the real compatibility unit

Date: 2026-07-04

Yoke must not treat `provider="codex"` or `provider="claude"` as enough information to decide feature support. The compatibility unit is the provider surface: Codex app server, Codex CLI, Codex SDK, Claude Agent SDK, Claude Code CLI, and any future app/server API can expose different options, event streams, auth paths, session models, and feature gates.

This matters because Codex app server appears to be the richest Codex surface for CodeAlmanac-style harness use: it exposes app-server sessions, streaming events, MCP-style tools, experimental API flags, and thread lifecycle details that are not necessarily available through every Codex CLI or SDK path. Claude has its own split between Claude Code CLI behavior and the Agent SDK surface; workflows, subagents, skills, hooks, permissions, and session continuation must be checked against the exact surface we are using.

Design rule: every Yoke capability should answer four questions:

1. Which surface exposes it?
2. Is it native, emulated, or unavailable on that surface?
3. What is the exact option/event/session shape Yoke maps to?
4. What happens when the caller asks for it on a weaker surface?

Concrete implication: `profile_for("codex:app-server")`, `profile_for("claude:sdk")`, and future CLI profiles should be first-class. Capability docs and tests should avoid broad claims such as "Codex supports goals" unless they name the surface and the mechanism. The public API can stay simple, but the implementation and docs should preserve surface-level truth.

This note should keep pressure on the design while building workflows, goals, subagents, skills, sessions, streaming, and auth. Yoke is allowed to expose one pleasant model, but it must not hide provider-surface differences that change behavior.
