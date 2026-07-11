# Codex app-server server requests are visible Yoke events

Date: 2026-07-04

Codex app-server is bidirectional JSON-RPC. During a turn, the server can send requests to the client for approvals, user input, MCP elicitation, dynamic tool calls, and permission profile decisions. Yoke already answered those requests noninteractively, but the events were invisible to embedders.

Yoke now emits normalized events for server-initiated app-server requests before sending the existing noninteractive response:

- command, file-change, patch, exec, and permission approval requests -> `Event(kind="approval_request")`.
- user-input and MCP elicitation requests -> `Event(kind="user_input_request")`.
- other handled server tool requests -> `Event(kind="tool_request")`.
- `serverRequest/resolved` notifications -> `Event(kind="request_resolved")`.

The current policy still declines/denies or returns empty answers exactly as before. This slice changes visibility, not approval behavior. Embedders such as CodeAlmanac can now render that Codex asked for approval or input, even when Yoke is running in noninteractive mode.

Official docs checked:

- https://developers.openai.com/codex/app-server
- https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md

Follow-up: `CodexAppServerOptions(request_handler=...)` now provides a low-level provider-specific callback; see `docs/notes/0136-codex-app-server-request-policy.md`.
