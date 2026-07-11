# Feature rows across surfaces

Date: 2026-07-04

Yoke now exposes a feature-first view on provider reports:

```python
rows = matrix_for("codex").feature(Feature.STREAMING)
```

Each row is a `SurfaceFeature` with `provider`, `surface`, `channel`, `runnable`, `feature`, `support`, `note`, `lowering`, `recipes`, and `evidence`.

This exists because "Claude supports X" and "Codex supports X" are usually incomplete statements. The useful question is "which Claude or Codex surface supports X, how directly, and with what lowering?" For example, Codex app-server is the deep integration protocol for authentication, conversation history, approvals, and streamed agent events. The Codex Python SDK controls a local app-server over JSON-RPC, while the CLI has interactive features such as `/goal` and `/agent` that are not the same as SDK methods. Claude Python SDK, Claude TypeScript SDK, and Claude CLI likewise expose different combinations of sessions, interrupts, workflows, hooks, skills, and subagents.

Use `matrix_for(provider).feature(feature)` when researching or integrating a capability that is likely to differ by surface. Use `profile_for(provider, surface)` or `report_for(provider, surface)` when the surface is already chosen.

Sources checked in this slice:

- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/cli/features
- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/hooks-guide
