# Surface capability matrix

Yoke now keeps surface capability truth in `src/yoke/surfaces.py`.

This is deliberately separate from provider adapters. Adapters execute a surface; `surfaces.py` records what Yoke currently believes about the surface. That lets us answer capability questions even for tracked surfaces that do not have built-in adapters yet, such as `claude_typescript_sdk` and `codex_typescript_sdk`.

Research deltas from this slice:

- Codex must stay surface-aware. The Codex manual separates CLI, app, app-server, SDK, custom agents, skills, hooks, MCP, and subagents. Yoke should not collapse those into one `codex` capability table.
- Codex app-server remains the richest local Codex surface for Yoke: live sessions, streaming notifications, `model/list`, native thread goals, skill roots, hooks/MCP config, and collab-agent tool calls.
- Codex CLI supports native provider skills, hooks, MCP, and `.codex/agents/*.toml` custom agent files. Yoke direct CLI runs still compile inline Yoke declarations into prompt text unless the caller explicitly writes provider artifacts with `bundle().write(...)`.
- Claude Python SDK subagents are native, not compiled. Yoke maps declared subagents to Claude SDK `AgentDefinition` values. Claude also supports filesystem-based subagents, but programmatic definitions are the stronger SDK-native shape for Yoke.
- Claude plugins are the native way to load folder skills through the SDK. Plugin paths point at the plugin root, not directly at a skill folder.
- Claude dynamic Workflow appears TypeScript-SDK-native. Yoke Python workflows remain emulated over provider turns for now, so the matrix marks `claude_typescript_sdk` workflow as native and `claude_python_sdk` workflow as emulated with a note.

Design implication:

`capabilities_for(provider, surface)` should stay public and small. `Harness(...).capabilities()` asks the selected adapter, while `capabilities_for(...)` lets docs, tests, and future integrations inspect a surface before a built-in adapter exists.
