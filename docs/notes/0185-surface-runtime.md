# Surface runtime is separate from channel

Date: 2026-07-04

Yoke reports now include `runtime` beside `channel`.

`channel` answers how the caller enters the provider surface. Examples: `sdk`, `cli`, `app_server`.

`runtime` answers what provider machinery backs that surface. Examples: `codex_app_server`, `codex_exec`, `claude_code`.

This distinction matters for Codex. The Codex Python SDK is an SDK channel, but OpenAI documents it as controlling the local Codex app-server over JSON-RPC. Codex app-server itself is the rich integration protocol for authentication, conversation history, approvals, and streamed agent events. Codex CLI remains a separate exec-oriented surface with interactive behaviors such as `/goal` and `/agent` that are not automatically Python SDK methods.

Claude has a similar but less split-looking shape. Claude Python SDK, Claude TypeScript SDK, and Claude CLI are different entrypoints, but they all sit over Claude Code machinery. The Python SDK has two different control levels inside the same surface: `query()` creates a fresh managed exchange, while `ClaudeSDKClient` is for continuous conversations and interrupts.

Current runtime mapping:

- `claude_python_sdk` -> `claude_code`
- `claude_typescript_sdk` -> `claude_code`
- `claude_cli` -> `claude_code`
- `codex_cli` -> `codex_exec`
- `codex_python_sdk` -> `codex_app_server`
- `codex_typescript_sdk` -> `codex_sdk`
- `codex_app_server` -> `codex_app_server`

This field is descriptive metadata. It does not imply feature inheritance. A surface can share a runtime and still expose a narrower public API. Keep checking feature support with `profile.support_for(...)`, `report_for(...)`, or `matrix_for(...).feature(...)`.

Sources checked:

- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/app-server
- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/typescript
