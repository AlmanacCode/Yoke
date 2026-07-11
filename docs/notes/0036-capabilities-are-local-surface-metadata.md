# Capabilities are local surface metadata

Date: 2026-07-04

Yoke should let callers ask a harness what the selected provider surface can do without starting a provider run.

`Harness.capabilities()` and `Session.capabilities()` now return the adapter's local capability matrix:

```python
harness = Harness(
    provider="codex",
    surface="codex_app_server",
    agent=agent,
    cwd=repo,
)

caps = harness.capabilities()
caps.support_for(Feature.READABLE_GOAL)
caps.supports(Feature.MODELS)
```

This is deliberately different from `await harness.models()`.

Capabilities are Yoke's known support matrix for the selected adapter surface. They should not require auth, a live provider process, network access, or a model-list request.

Model listing is a provider call because it depends on the user's account and current provider state. Codex app-server can answer it through `model/list`; Codex CLI and Claude currently report it as unsupported in Yoke.

This distinction keeps the public API honest:

- `capabilities()` answers "does this surface support the feature in principle?"
- `models()` answers "what models does this account expose right now?"
