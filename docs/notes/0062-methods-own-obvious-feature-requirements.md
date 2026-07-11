# Methods own obvious feature requirements

Date: 2026-07-04

Some Yoke methods imply a feature requirement without the caller spelling it out:

- `Harness.start(...)` implies `Feature.SESSION`.
- `Harness.workflow(...)` implies `Feature.WORKFLOW`.
- `Harness.models(...)` implies `Feature.MODELS`.

These methods now route through `Harness.require(...)` before touching an adapter. If the harness has no explicit surface, Yoke chooses the best runnable surface for the implied feature. If the caller pinned a surface, Yoke validates it and raises `UnsupportedFeature` instead of falling into an adapter that cannot satisfy the operation.

Plain `Harness.run(...)` intentionally does not auto-select by `Feature.ONE_SHOT`. One-shot runs are the cheapest path, and provider defaults should stay unsurprising unless the caller asks for richer behavior.

This keeps the public API readable:

```python
models = Harness(provider="codex", agent=agent, cwd=repo).models_sync()
```

The call can select `codex_app_server` because model listing is not a CLI feature in Yoke's current matrix.
