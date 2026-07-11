# Channel filtering

Date: 2026-07-04

## Change

Yoke now lets callers filter provider surfaces by broad exposure channel:

```python
profiles_for("codex", channel="sdk")
reports_for("claude", channel=Channel.CLI)
fits_for("codex", requires=[Feature.STREAMING], channel=Channel.SDK)
select_profile("codex", requires=[Feature.READABLE_GOAL], channel=Channel.APP_SERVER)
```

## Rule

`Channel` narrows candidates. `Surface` still proves features.

This matters because `codex_python_sdk` and `codex_app_server` are related, but they should not be treated as feature-identical. The Python SDK controls local Codex app-server over JSON-RPC, but Yoke's app-server adapter exposes lower-level thread goal methods, request handling, and event normalization that are not automatically part of the SDK surface.

## Why this belongs in Yoke

The user often thinks in exposure paths first:

- "I want the app-server integration because it has streaming and goals."
- "Show me SDK-backed surfaces only."
- "Avoid CLI behavior in this embedded product."

Yoke should support that vocabulary without weakening the exact capability matrix.

## Boundary

Do not use `channel=Channel.SDK` as a shorthand for a feature set. SDK-backed surfaces can differ by language and provider. Use `requires=[Feature.X]` for feature requirements and `channel=...` only for exposure-path constraints.
