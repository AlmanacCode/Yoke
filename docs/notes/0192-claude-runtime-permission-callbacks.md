# 0192 - Claude runtime permission callbacks

Claude permissions are split across serializable rules and live SDK callbacks.
Yoke now models that split directly.

`ClaudeOptions.permission_mode`, `allowed_tools`, and `disallowed_tools` are
normal provider options because they serialize cleanly and can appear in folder
source. `ClaudeOptions.can_use_tool` and `ClaudeOptions.hooks` are runtime-only
because they can contain Python callbacks. They are excluded from
`model_dump()`, appear in `RunOptions.runtime_options()`, and are still passed to
`ClaudeAgentOptions` for real SDK execution.

Raw dict provider options accept both Python and TypeScript spelling for the
callback: `can_use_tool` and `canUseTool`. Yoke forwards the Python spelling to
Claude's Python SDK. Hook dictionaries are forwarded as-is because Claude's SDK
defines the matcher/callback structure.

This matches the surface rule for Yoke: the folder is durable source, while live
callbacks are an embedding concern. Provider-native permission options still
imply `Feature.CLAUDE_PERMISSIONS`; neutral `Permissions(...)` remains a
portable value unless the caller explicitly requires `Feature.PERMISSIONS`.

References:

- <https://code.claude.com/docs/en/agent-sdk/permissions>
- <https://code.claude.com/docs/en/agent-sdk/hooks>
