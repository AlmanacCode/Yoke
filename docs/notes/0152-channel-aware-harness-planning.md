# Channel-aware harness planning

Date: 2026-07-04

## Change

`Harness`, `Session`, and the surface planning model now understand channel constraints directly.

Examples:

```python
harness.plan(channel=Channel.APP_SERVER)
harness.require(channel=Channel.APP_SERVER)
harness.fits(Feature.STREAMING, channel=Channel.SDK)
session.require(channel="app_server")
```

`Plan` now carries:

- `channel`: the requested channel, if any.
- `channel_mismatch`: true when an explicit surface is already set but belongs to a different channel.

## Why this matters

The low-level helpers already accepted `channel=`, but most users will touch `Harness` and `Session`. Channel belongs there because the natural Yoke question is often:

- "Use a Codex app-server-backed surface for this session."
- "Show me SDK-backed fits for this requirement."
- "Do not silently switch my explicit CLI surface."

## Rule

If no surface is set, channel can select a surface. If a surface is already set, channel validates that exact surface. It does not silently replace it.

That keeps the Yoke contract predictable: explicit surface wins unless it contradicts the requested channel, in which case `plan().ok` is false and `require(...)` raises.

## Follow-up pressure

A later slice should consider whether `RunOptions` or `SessionOptions` need a provider channel hint. For now, channel is a selection concern on `Harness`, `Session`, and helper functions, not serialized agent configuration.
