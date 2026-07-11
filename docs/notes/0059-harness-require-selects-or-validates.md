# Harness.require selects or validates the surface

Date: 2026-07-04

Yoke now has a fluent way to connect feature requirements to harness selection:

```python
harness = Harness(
    provider="codex",
    agent=agent,
    cwd=repo,
).require(Feature.STREAMING, Feature.READABLE_GOAL)
```

If `surface` is unset, `require(...)` selects the best known profile for the provider. For Codex streaming plus readable goals, that means `codex_app_server`.

If `surface` is explicit, `require(...)` validates that exact surface and raises `UnsupportedFeature` when it cannot satisfy the requested features. It does not silently switch explicit surfaces.

This gives Yoke a clean beginner path without hiding operational reality:

- beginners can say what they need and let Yoke choose;
- advanced users can pin a surface and get a hard guard;
- applications can still inspect `harness.profile()` before running;
- runtime adapter availability remains separate from conceptual capability selection.
