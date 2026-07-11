# Provider surfaces research refresh

2026-07-04

Yoke must keep modeling capabilities at the surface level.

OpenAI documents Codex app-server as the deep product integration surface for authentication, conversation history, approvals, and streamed agent events. The same docs point automation and CI users toward the Codex SDK instead. The Python SDK docs say the Python package controls a local Codex app-server over JSON-RPC and ships a pinned Codex CLI runtime. That means `codex_cli`, `codex_python_sdk`, and `codex_app_server` are related but not interchangeable Yoke surfaces.

Claude documents different control levels inside its Agent SDK. Python `query()` creates a managed one-off exchange by default, while `ClaudeSDKClient` reuses the same session and supports interrupts. The TypeScript SDK currently exposes extra helpers such as `startup()`, session listing/message reading, and the documented Workflow tool. Claude subagents, skills, and hooks are also first-class Claude Code concepts with filesystem and SDK forms.

Yoke should therefore keep a portable public shape while exposing honest surface behavior:

- `native` means the selected surface has a direct provider primitive.
- `compiled` means Yoke translates the concept into instructions or provider files.
- `emulated` means Yoke owns orchestration across multiple provider turns.
- `unknown` means the surface exists conceptually but Yoke has not verified the support contract.
- `unsupported` means the selected surface should reject the feature.

This slice adds evidence URLs to `SurfaceReport` so applications can show which provider docs anchor a matrix row.

Sources:

- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/cli/reference
- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks
