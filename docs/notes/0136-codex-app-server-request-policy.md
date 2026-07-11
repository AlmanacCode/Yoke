# Codex app-server request policy is a provider-specific callback

Date: 2026-07-04

Yoke now lets embedded apps override Codex app-server server-request responses with `CodexAppServerOptions(request_handler=...)`.

The callback receives two arguments:

- the normalized Yoke `Event` for the server request
- the default `ServerResponse` Yoke would use in noninteractive mode

The callback may return:

- `None` to keep the default response
- a JSON object to send as the JSON-RPC result
- `ServerResponse(result=...)` or `ServerResponse(error=...)` for explicit result/error control

This is intentionally provider-specific. Codex app-server requests are JSON-RPC client-interaction pressure: command/file approvals, MCP elicitation, dynamic tool calls, permissions, and user input. They do not map cleanly to Claude's hook system or portable agent options.

Session-level `CodexAppServerOptions` carry into later turns. A run-level `RunOptions(provider=ProviderOptions(codex=...))` can override them for a single turn.

The default remains safe and noninteractive: approvals are declined/denied and user-input forms receive empty/declined responses unless the embedder provides a handler.

Next pressure test: expose a higher-level convenience policy for common cases such as "approve read-only commands", "ask a human", or "deny destructive edits", while keeping the low-level callback available for apps like CodeAlmanac.
