# 0191 - Permission options participate in planning

Yoke now treats explicit permission controls as feature requirements.

New features:

- `Feature.PERMISSIONS`
- `Feature.CODEX_PERMISSIONS`
- `Feature.CLAUDE_PERMISSIONS`

`Feature.PERMISSIONS` exists for callers that explicitly want to require a
surface with neutral permission support. `RunOptions.permissions` and
`SessionOptions.permissions` do not imply it automatically, because custom
adapters and workflow tests often use neutral permissions as data to forward.

Provider-native option fields imply provider-specific permission features:

- `ClaudeOptions.permission_mode`, `allowed_tools`, or `disallowed_tools`
  imply `Feature.CLAUDE_PERMISSIONS`.
- `CodexOptions.sandbox`, `approval`, `approvals_reviewer`, `network`, or
  `writable_roots` imply `Feature.CODEX_PERMISSIONS`.
- Raw dict aliases such as `permissionMode`, `allowedTools`,
  `approvalPolicy`, `networkAccess`, and `writableRoots` do the same.

This matters for auto-surface selection. A Codex run with
`CodexOptions(sandbox=...)` now plans against `codex_app_server`, because that
is the Yoke surface that lowers those fields into app-server turn parameters.
Neutral `Permissions(access=..., approval=...)` do not require
`codex_permissions` and do not affect planning by default. If a caller
explicitly requires `Feature.PERMISSIONS`, auto planning may choose the
strongest runnable fit, while an explicit simpler surface such as `codex_cli`
validates when it supports `permissions`.

This is not a portable policy abstraction. It is a planning signal that keeps
native provider options from being invisible.
