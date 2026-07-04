# Claude event mapping

Yoke now maps Claude Python SDK messages into the same small event language used by other adapters where the mapping is clear:

- `SystemMessage` -> `provider_session`
- `AssistantMessage` text blocks -> `text`
- `AssistantMessage.usage` -> `usage`
- `ResultMessage.result` -> `result`
- `ResultMessage.structured_output` -> `text`
- `ResultMessage.usage` -> `usage`
- `ResultMessage` completion -> `done`
- `StreamEvent` -> `stream_event`
- `HookEventMessage` -> `hook`
- `RateLimitEvent` -> `rate_limit`

The raw Claude SDK message is still preserved on every event.

This is intentionally conservative. Yoke does not yet normalize Claude tool use blocks into `Tool` display metadata because the current CodeAlmanac need is reliable text/result/usage/session rendering. Tool block mapping should be a separate slice with real examples.

The important behavior change is that `Session.stream(...)` for Claude now yields normalized Yoke events instead of only `AssistantMessage` and `ResultMessage` class names.
