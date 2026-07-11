# 0188 - Control status is surface-specific

Yoke now reports runtime control metadata with `status.control`.

The report is intentionally about the selected provider surface, not the broad
provider family. Codex app-server has native model, interrupt, fork, and
experimental API controls, but it reuses existing Codex authentication. Codex
Python SDK can initiate login, but it does not expose every app-server feature
as a public SDK affordance. Claude Agent SDK exposes permissions, hooks, and
runtime callbacks through SDK options, but Yoke currently treats Claude auth as
external provider setup.

`ControlMode.PROGRAMMATIC` means Yoke can initiate login for that surface.
`ControlMode.EXTERNAL_AUTH` means at least one live runtime control is native,
but authentication is handled through the provider's normal setup.
`ControlMode.UNKNOWN` means Yoke has incomplete metadata for a custom or
untracked surface.

This keeps safety honest. Codex sandbox mode and approval policy are separate
provider controls, not implied by a Yoke login or interrupt feature. Claude
permission modes, allow/deny rules, hooks, and `canUseTool` callbacks remain
provider options until Yoke has a first-class policy model.

References:

- https://developers.openai.com/codex/auth
- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/concepts/sandboxing
- https://code.claude.com/docs/en/agent-sdk/permissions
