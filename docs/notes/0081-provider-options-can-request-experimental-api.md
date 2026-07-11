# Provider options can request experimental API

`Feature.EXPERIMENTAL_API` should be reachable through normal Yoke options, not only through manual `Harness.require(...)` calls.

`CodexOptions(experimental_api=True)` and raw `{"experimentalApi": true}` now imply `Feature.EXPERIMENTAL_API`. This makes `Harness(provider="codex").plan(RunOptions(provider=...))` select `codex_app_server`, because that is the Yoke surface that initializes app-server with `capabilities.experimentalApi = true`.

This follows the option-design rule: user intent lives in `RunOptions`, `SessionOptions`, `WorkflowOptions`, and `ProviderOptions`; surface selection is derived from those options. Provider-specific options remain provider-scoped, so a Codex-only experimental flag does not pressure Claude planning.

The spelling is intentionally Pythonic (`experimental_api`) with camel-case input accepted for JSON/app-server-adjacent configuration (`experimentalApi`).
