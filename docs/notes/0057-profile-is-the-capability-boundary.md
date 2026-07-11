# Profile is the capability boundary

Date: 2026-07-04

Yoke now exposes a `Profile` model for the resolved `(provider, surface)` pair.

```python
from yoke import Feature, profile_for

profile = profile_for("codex", "codex_app_server")
assert profile.supports(Feature.STREAMING)
```

`Capabilities` remains the raw feature matrix. `Profile` is the user-facing answer to: "what exact harness surface am I using, and what does it support?"

This matters because Codex and Claude do not expose the same features through every entrypoint. Codex app-server, Codex CLI, Codex SDKs, Claude CLI, and Claude SDKs are separate operational surfaces. A provider-only capability model would hide the actual risk.

Public SDK rule:

- Use `profile_for(provider, surface)` when choosing or displaying a surface.
- Use `Harness.profile()` and `Session.profile()` inside applications.
- Keep `Harness.capabilities()` as a convenience/back-compat raw matrix method.
- Do not infer app-server behavior from CLI support or SDK support.

This is especially important for goals, streaming events, model listing, collaboration agent tools, filesystem agents, skills, workflows, and structured output.
