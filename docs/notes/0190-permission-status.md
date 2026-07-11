# 0190 - Permission status reports

Yoke now exposes `status.permissions`.

The report is intentionally surface-specific:

- Codex surfaces report `PermissionMode.CODEX_NATIVE`.
- Claude SDK surfaces report `PermissionMode.CLAUDE_NATIVE`.
- Claude CLI reports `PermissionMode.EXTERNAL` because the current Yoke adapter
  does not own that surface's permission configuration.
- Custom surfaces report `PermissionMode.UNKNOWN`.

The field names are provider-native on purpose. Codex has `sandbox`,
`approval`, `network`, and `approval_reviewer` controls. Claude SDK has
`permission_mode`, `tool_rules`, `hooks`, `callbacks`, and `dynamic` permission
mode changes.

This report makes the previous native option slice discoverable. Users can now
ask a surface what kind of permission model it honors before choosing
`Permissions`, `ClaudeOptions`, or `CodexOptions`.

This still is not a portable policy abstraction. A portable policy should only
exist if it can preserve Codex's sandbox/approval split and Claude's
hook/rule/callback evaluation chain without flattening away important safety
semantics.

References:

- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/concepts/sandboxing
- https://code.claude.com/docs/en/agent-sdk/permissions
