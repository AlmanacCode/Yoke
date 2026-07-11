# Capability reports carry feature-level evidence

Date: 2026-07-04

Yoke capability reports now include a stable surface key and evidence on each feature row.

Before this slice, `SurfaceReport` had provider-level evidence only. That was not enough for Yoke's core design problem: the same provider exposes different features through different surfaces. A user comparing `codex:cli`, `codex:codex_python_sdk`, and `codex:codex_app_server` needs to see why a feature is native, compiled, emulated, unsupported, or unknown on that exact surface.

`SurfaceReport.key` is now the compact `provider:surface` identity. Each `FeatureReport` carries its own `evidence` tuple. Feature evidence falls back to the surface evidence when Yoke has not recorded more precise sources.

Concrete examples:

- `codex:codex_app_server` reports `readable_goal` as native with Codex app-server evidence.
- `codex:codex_cli` reports `readable_goal` as unsupported.
- `claude:claude_python_sdk` reports `inline_subagents` as native with Claude Agent SDK subagent evidence.
- `codex:codex_app_server` reports `collab_agent_tools` with both Codex subagent and app-server evidence because the docs split concept and event surface.

Current docs checked during this slice:

- Codex app-server documents streamed thread, turn, item, and server request notifications, plus `serverRequest/resolved`.
- Codex SDK documents TypeScript thread start/resume/run and Python control of local app-server over JSON-RPC.
- Codex subagents are surfaced in Codex app and CLI and require explicit prompting.
- Claude Agent SDK subagents are defined through `agents` in SDK options and can also load filesystem agents.
- Claude Agent SDK skills are filesystem artifacts, not programmatic registrations.
- Claude Agent SDK hooks include Python-supported hook events and subagent lifecycle hooks.

Design implication: every future feature claim should be encoded at the feature/surface level when the source is specific. Yoke should not let a provider-wide sentence substitute for a surface-specific capability.
