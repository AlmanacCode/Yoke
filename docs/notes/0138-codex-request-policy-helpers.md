# Codex request policy helpers are app-server-specific

Date: 2026-07-04

Yoke now has `CodexRequestPolicy` and `CodexApprovalDecision` for the app-server request-handler seam.

The helper is deliberately named for Codex app-server behavior. It handles modern app-server approval request methods only:

- `item/commandExecution/requestApproval`
- `item/fileChange/requestApproval`

It does not guess responses for legacy methods such as `execCommandApproval` or `applyPatchApproval`. Those fall back to Yoke's existing safe default response. This keeps approval behavior evidence-backed instead of pretending every Codex surface exposes the same protocol.

Current docs pressure: Codex documents app-server as a JSON-RPC surface with initialization capabilities, streamed notifications, server requests, `serverRequest/resolved`, and request approval decisions. Codex SDK is documented as controlling the local app-server over JSON-RPC, but it is still a separate user-facing surface with its own public API. Codex subagent docs say subagent activity is surfaced in the app and CLI, with IDE visibility coming later. Claude Agent SDK docs expose subagents via the `agents` parameter, while Claude skills remain filesystem artifacts loaded through setting sources.

Design implication: Yoke should keep adding portable models only where the semantics survive across surfaces. For anything lifecycle-sensitive, expose a small portable API plus surface-specific options, event evidence, and readiness reports.

Sources checked on 2026-07-04:

- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/subagents
- https://code.claude.com/docs/en/agent-sdk/overview
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/agent-sdk/skills
