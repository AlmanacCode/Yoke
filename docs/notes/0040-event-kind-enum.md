# Event kind enum

Date: 2026-07-04

Yoke now exposes `EventKind` for normalized event names:

```python
event.kind is EventKind.TOOL_USE
event.kind == "tool_use"
```

`Event.kind` remains `EventKind | str`.

That is intentional. Yoke should make common normalized events typed and discoverable without blocking provider-specific event names that Yoke has not modeled yet.

Typed kinds:

- `text_delta`
- `text`
- `tool_use`
- `tool_result`
- `tool_summary`
- `context_usage`
- `provider_session`
- `warning`
- `error`
- `done`
- `hook`
- `rate_limit`
- `stream_event`
- `unknown`

This follows the same design as capabilities: Yoke names the stable cross-provider vocabulary and leaves explicit escape hatches for provider-specific strength.
