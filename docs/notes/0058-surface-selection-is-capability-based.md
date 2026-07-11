# Surface selection is capability-based

Date: 2026-07-04

Yoke now exposes surface selection helpers:

```python
from yoke import Feature, select_profile

profile = select_profile(
    "codex",
    requires=[Feature.READABLE_GOAL, Feature.STREAMING],
)
assert profile.surface == "codex_app_server"
```

The selector uses the capability matrix, not the adapter registry.

That is deliberate. The adapter registry answers: "can this Yoke installation run this surface right now?" The profile selector answers: "which provider surface is conceptually the right surface for these features?"

These are different questions. Claude TypeScript SDK can be the best surface for native workflow support even if the current Python package has not implemented a TypeScript adapter. Codex app-server can be the best surface for readable/mutable goals even when a simpler CLI run would be enough for a one-shot implementation task.

Selection rule:

- `native` support scores highest.
- `compiled` support is next.
- `emulated` support is usable but weaker.
- `unknown` and `unsupported` cannot satisfy required features.
- Ties prefer the profile with broader total known support.

This keeps Yoke honest about provider strengths without forcing every caller to memorize which CLI, SDK, or app-server surface exposes which primitive.
