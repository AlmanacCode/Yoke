# Login is a programmatic capability

Date: 2026-07-04

Yoke now has `Feature.LOGIN`.

The feature means: this surface can start a login/auth flow through Yoke. It does not mean the provider can be authenticated somehow.

Current matrix:

- `codex_python_sdk`: native login. The adapter exposes ChatGPT, device-code, and API-key flows.
- `codex_cli`: unsupported for Yoke login. Users run `codex login` externally.
- `codex_app_server`: unsupported for Yoke login. It uses existing Codex authentication.
- `claude_python_sdk`: unsupported for Yoke login. Users set `ANTHROPIC_API_KEY` or authenticate Claude Code externally.
- `claude_cli`: unsupported for Yoke login. It is an external interactive flow.

`Harness.login(...)` now routes through `Harness.require(Feature.LOGIN)`. With no explicit surface, `Harness(provider="codex", ...).login("device_code")` selects `codex_python_sdk`. With an explicit unsupported surface, Yoke raises `UnsupportedFeature` before adapter invocation.

This keeps auth language honest: readiness checks answer whether the provider is currently usable; login capability answers whether Yoke can initiate the auth flow.
