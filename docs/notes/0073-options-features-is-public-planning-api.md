# Options.features is public planning API

Date: 2026-07-04

`RunOptions.features(...)`, `SessionOptions.features(...)`, `WorkflowOptions.features(...)`, and `ProviderOptions.features(...)` now return `tuple[Feature, ...]`.

This is public SDK surface, not just internal plumbing. Applications can inspect option-driven requirements before they execute a run:

```python
features = RunOptions(output_schema=Summary).features(provider="codex")
fits = harness.fits(*features)
```

The method remains on the option models because the option model owns the feature pressure it creates. Harness and Session consume it, but application code can too.
