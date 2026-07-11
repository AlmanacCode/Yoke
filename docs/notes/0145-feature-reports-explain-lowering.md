# Feature reports explain lowering behavior

Date: 2026-07-04

Yoke feature reports now include `lowering`.

`support` answers "how direct is this surface's support?" with `native`, `compiled`, `emulated`, `unsupported`, or `unknown`. That was not enough for ambiguous agent concepts. `lowering` now explains what Yoke actually does for the feature on that surface.

Examples:

- `codex:codex_cli` declared subagents compile into prompt text for direct runs, while `bundle()` can write `.codex/agents/*.toml` custom-agent files.
- `codex:codex_app_server` collab agent tools are native provider events such as `collabAgentToolCall`, normalized into `AgentCall` event payloads.
- `claude:claude_python_sdk` inline subagents become Claude SDK `AgentDefinition` values in query options.
- `claude:claude_python_sdk` workflows are Yoke-owned SDK turns, not Claude's TypeScript-native `Workflow` tool.
- `claude:claude_typescript_sdk` tracks the native Workflow tool as a distinct capability, even though Yoke's current Python adapter does not run that surface.

Provider docs checked during this slice:

- Codex subagents: https://developers.openai.com/codex/subagents
- Codex workflows: https://developers.openai.com/codex/workflows
- Claude Agent SDK subagents: https://code.claude.com/docs/en/agent-sdk/subagents
- Claude Agent SDK skills: https://code.claude.com/docs/en/agent-sdk/skills

Design implication: Yoke should not rely on support levels alone for user understanding. Two surfaces can both say "compiled" while lowering through different mechanisms. Future features should add lowering text whenever the same Yoke noun maps to different provider primitives.
