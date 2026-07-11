# Runnable and conceptual surfaces are different

Date: 2026-07-04

Yoke profiles now carry `runnable`.

A profile can be conceptually best without being runnable by this Python package today. The example that forced the distinction is Claude workflows:

```python
profile = select_profile("claude", requires=[Feature.WORKFLOW])
assert profile.surface == "claude_typescript_sdk"
assert not profile.runnable
```

The Claude TypeScript SDK is the conceptually native workflow surface, but Yoke does not yet ship a TypeScript adapter. The capability matrix should still know that truth. Runtime ergonomics should not accidentally route a Python `Harness.run(...)` into an unavailable adapter.

For runnable Python execution, `Harness(provider="claude").require(Feature.WORKFLOW)` selects `claude_python_sdk` because Yoke can emulate workflows over Claude Python SDK turns. That is weaker than native TypeScript workflow support, but it is runnable and honest.

Rules:

- `select_profile(..., runnable=None)` is conceptual by default and may return non-runnable surfaces.
- `select_profile(..., runnable=True)` only returns surfaces with a Yoke adapter path.
- `profiles_for(provider, runnable=True)` lists Python-runnable surfaces.
- `Harness.require(...)` uses runnable selection by default because it sits on a run-capable object.
- `Harness.require(..., runnable=False)` is an explicit planning escape hatch.

This keeps two questions separate:

- Which provider surface naturally supports this primitive?
- Can this installed Yoke package run that surface right now?

Do not collapse these. The whole SDK is trying to be honest about Claude/Codex surface differences without making the beginner path sharp.
