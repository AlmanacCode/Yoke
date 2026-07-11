# App-server experimental API is a capability

Official Codex docs now make the surface split sharper: the Python SDK controls local Codex app-server over JSON-RPC, while the app-server protocol itself has a stable surface and an opt-in experimental surface.

Yoke already initializes Codex app-server with `capabilities.experimentalApi = true`. That should be visible in the capability language, not hidden inside adapter setup.

`Feature.EXPERIMENTAL_API` means a surface can use provider APIs that require the app-server experimental opt-in. Today Yoke marks it native only on `codex_app_server`. The public Codex Python SDK is app-server-backed, but Yoke does not expose raw experimental app-server methods through `codex_python_sdk`, so that surface remains unsupported for this feature.

Sources checked on 2026-07-04:

- OpenAI Codex SDK docs: https://developers.openai.com/codex/sdk
- OpenAI Codex app-server README: https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
- Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk/overview

Design consequence: when a future Yoke method needs app-server-only experimental protocol, it should require `Feature.EXPERIMENTAL_API`. That will select `codex_app_server` and avoid pretending the generic Codex provider or Python SDK surface can satisfy the same contract.
