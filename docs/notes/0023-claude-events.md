# Claude event mapping

Yoke now maps Claude Python SDK messages into the same small event language used by other adapters where the mapping is clear:

- `SystemMessage` -> `provider_session`
- `AssistantMessage` text blocks -> `text`
- `AssistantMessage` tool use blocks -> `tool_use`
- `AssistantMessage` tool result blocks -> `tool_result`
- `AssistantMessage.usage` -> `usage`
- `ResultMessage.result` -> `result`
- `ResultMessage.structured_output` -> `text`
- `ResultMessage.usage` -> `usage`
- `ResultMessage` completion -> `done`
- `StreamEvent` -> `stream_event`
- `HookEventMessage` -> `hook`
- `RateLimitEvent` -> `rate_limit`

The raw Claude SDK message is still preserved on every event.

This is still intentionally conservative. Yoke now normalizes Claude tool blocks where the SDK exposes clear typed fields, but background task messages remain a separate slice because they represent subagent/background execution rather than ordinary inline tool calls.

The important behavior change is that `Session.stream(...)` for Claude now yields normalized Yoke events instead of only `AssistantMessage` and `ResultMessage` class names.
