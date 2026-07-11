# 0189 - Native permission options

Yoke now keeps simple neutral permissions and provider-native permission
controls side by side.

`Permissions(access=..., approval=..., network=...)` remains the portable,
small API. It is good for common read/write/full access and ask/auto/never
approval posture.

Claude-specific controls live on `ClaudeOptions`:

- `permission_mode`
- `allowed_tools`
- `disallowed_tools`

These map to Claude Agent SDK `permission_mode`, `allowed_tools`, and
`disallowed_tools`. They preserve Claude's native model where permission modes,
allow/deny rules, hooks, and `canUseTool` callbacks are separate parts of the
evaluation chain.

Codex-specific controls live on `CodexOptions`:

- `sandbox`
- `approval`
- `approvals_reviewer`
- `network`
- `writable_roots`

For Codex app-server turns, Yoke uses these fields when building
`approvalPolicy` and `sandboxPolicy`. Neutral `Permissions.network=True` now
also flows into Codex app-server `sandboxPolicy.networkAccess`.

This slice deliberately does not add a portable `Policy` abstraction. Codex and
Claude do not expose the same safety model. A future Yoke policy layer should be
added only after we can prove the names remain honest across both providers.

References:

- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/concepts/sandboxing
- https://code.claude.com/docs/en/agent-sdk/permissions
