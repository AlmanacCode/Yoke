# Provider exposure channels

Date: 2026-07-04

## Discovery

Codex and Claude both expose agent harness behavior through multiple entrypoints. Those entrypoints do not have identical feature depth.

Codex docs now separate:

- CLI: interactive/headless terminal runs, resumable exec threads, JSONL events, filesystem custom agents.
- SDK: programmatic automation. The Python SDK controls the local app-server over JSON-RPC and ships with a pinned Codex CLI runtime.
- App server: deep product integration with authentication, conversation history, approvals, and streamed agent events.

Claude docs separate:

- CLI: Claude Code's filesystem-based `.claude/` behavior.
- Python SDK: programmable Claude Code agent loop with programmatic subagents, skills, hooks, sessions, and streaming.
- TypeScript SDK: documented native Workflow tool surface.

## Yoke change

Yoke now distinguishes two levels:

- `Surface`: exact entrypoint, such as `codex_app_server` or `claude_python_sdk`.
- `Channel`: broad exposure path, currently `cli`, `sdk`, `app_server`, or `custom`.

`Profile` and `SurfaceReport` now include `channel`, so `harness.profile()` and `harness.report()` can explain both the exact surface and the broad way the provider exposes it.

## Why this is right

The user-facing question is often broad: "is this SDK-backed?" or "does this need app-server?" The implementation question is exact: `codex_python_sdk` and `codex_app_server` both touch app-server mechanics, but their public knobs differ. `Channel` answers the broad question without erasing the exact `Surface`.

## Sources checked

- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/use-cases/follow-goals
- https://code.claude.com/docs/en/agent-sdk/claude-code-features
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/workflows

## Follow-up pressure

When Yoke grows a TypeScript adapter or deeper Codex SDK adapter, do not infer capability support from `Channel.SDK`. Keep capability checks on exact `Surface`, and use `Channel` only for explanation, filtering, and docs.
