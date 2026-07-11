# Runtime-only options are visible in the SDK

Date: 2026-07-04

Yoke now exposes runtime-only option reporting.

The first concrete case is `CodexAppServerOptions.request_handler`. It is a live Python callback used to answer Codex app-server server requests. It cannot be represented in a Yoke folder, YAML frontmatter, or provider-native filesystem artifact. Pydantic already excluded it from `model_dump()`, but that made the boundary too quiet.

`RuntimeOption` and `runtime_options(...)` now report active SDK-only fields. Option objects also expose `.runtime_options()`, so callers can inspect the object they already hold:

```python
options.runtime_options()
```

For a nested run option, the report path is explicit:

```text
provider.codex.app_server.request_handler
```

Design implication: Yoke's folder API and Python SDK should be peers where a value is serializable. Live callbacks, open handles, clients, and process objects should stay SDK-only and should be discoverable through reports rather than silently pretending to round-trip.

Current provider-doc pressure: Codex app-server exposes server requests and streamed notifications over JSON-RPC; Yoke's request handler is a Python-side policy hook around that protocol, not a provider-authored serializable setting. Codex SDK remains a separate public SDK surface that controls app-server behavior through code, so some options naturally belong in code.

Next pressure test: consider whether folder save should optionally warn or fail when an agent contains runtime-only options in a step `run:` override. For now the SDK exposes the report and README names the boundary.
