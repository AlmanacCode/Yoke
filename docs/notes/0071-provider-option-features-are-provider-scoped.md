# Provider option features are provider-scoped

Date: 2026-07-04

`ProviderOptions.features(provider=...)` now filters feature requirements to the active provider.

Codex-only options such as `collaborationMode` should pressure Codex harnesses toward `codex_app_server`; they should not make a Claude harness fail merely because the caller supplied a `ProviderOptions` object that also contains Codex settings.

Rules:

- `ProviderOptions.features()` with no provider returns all provider-option feature requirements.
- `ProviderOptions.features(provider="codex")` returns only Codex option requirements.
- `ProviderOptions.features(provider="claude")` ignores Codex options.
- `RunOptions`, `SessionOptions`, and `WorkflowOptions` pass their active provider through when called by `Harness` or `Session`.
- Raw collaboration keys only imply `Feature.COLLABORATION_MODE` inside the Codex provider section.

This keeps provider-specific options from leaking across provider boundaries while preserving the inspect-all behavior for diagnostics.
