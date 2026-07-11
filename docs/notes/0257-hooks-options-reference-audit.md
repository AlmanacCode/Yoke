# 0257 - Hooks and options reference audit

Date: 2026-07-04

## Short answer

Yoke should not flatten Claude and Codex into one hook or permission model.
Claude exposes live Python callbacks for hooks and permission prompts. Codex
exposes thread/turn options, app-server requests, app-server notifications, and
configured hook metadata. Yoke's current direction is right: share small
`Request` / `Response` payloads, keep provider-native options provider-scoped,
and document where each option enters the native surface.

## Claude Python SDK shape

Source snapshot: `/Users/rohan/Desktop/Projects/claude-agent-sdk-python`.

`ClaudeAgentOptions` exposes three separate tool controls:

- `tools`: the base set of built-in tools available to the model. A list limits
  built-ins, `[]` disables built-ins, and the `claude_code` preset restores the
  default Claude Code toolset.
- `allowed_tools`: auto-approval rules. These do not remove tools from the
  model; they let matching tools run without a prompt.
- `disallowed_tools`: removal rules. These tools are removed from context and
  cannot be used.

`permission_mode` is one of `default`, `acceptEdits`, `plan`,
`bypassPermissions`, `dontAsk`, or `auto`. `can_use_tool` is an async callback
for tool calls that reached an `ask` permission decision. It is not called for
already-allowed tool calls. `permission_prompt_tool_name` can route permission
prompts through an MCP tool instead of the normal handler.

Hooks are native live callbacks:

```python
hooks: dict[HookEvent, list[HookMatcher]] | None
```

The current hook event set is `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`,
`Notification`, `SubagentStart`, and `PermissionRequest`.

`HookMatcher` has `matcher`, `hooks`, and `timeout`. For tool hooks, `matcher`
can match tool names such as `Bash` or `Write|MultiEdit|Edit`. Multiple
matchers for the same event are dispatched concurrently by the Claude CLI.

Important hook output controls:

- `PreToolUse` can set `permissionDecision` to `allow`, `deny`, `ask`, or
  `defer`; it can also set `updatedInput` and `additionalContext`.
- `PostToolUse` can set `additionalContext` and `updatedToolOutput`; the older
  MCP-only `updatedMCPToolOutput` still exists.
- Common hook output can set `continue_`, `suppressOutput`, `stopReason`,
  `decision="block"`, `systemMessage`, and `reason`.
- `include_hook_events=True` streams hook lifecycle messages as
  `HookEventMessage` values.

Claude also exposes in-process MCP tools through `@tool` and
`create_sdk_mcp_server`. Those tools become MCP tools such as
`mcp__server__tool`; `allowed_tools` controls auto-approval for them, not
availability.

## Codex app-server and SDK shape

Source snapshot: `/Users/rohan/Desktop/Projects/openai-codex`.

The TypeScript SDK surface exposes simple thread options:

- `approvalPolicy`: `never`, `on-request`, `on-failure`, or `untrusted`
- `sandboxMode`: `read-only`, `workspace-write`, or `danger-full-access`
- `networkAccessEnabled`, `webSearchMode`, `webSearchEnabled`
- `additionalDirectories`, `workingDirectory`, `model`, and reasoning effort

Its public event stream is item-based: `thread.started`, `turn.started`,
`item.started`, `item.updated`, `item.completed`, `turn.completed`,
`turn.failed`, and `error`. Tool activity is represented as items such as
`command_execution`, `file_change`, `mcp_tool_call`, `web_search`, and
`todo_list`.

The Codex Python SDK exposes a narrower curated API over app-server:

- `ApprovalMode.auto_review` maps to `approvalPolicy=on-request` plus
  `approvalsReviewer=auto_review`.
- `ApprovalMode.deny_all` maps to `approvalPolicy=never`.
- `Sandbox.read_only`, `Sandbox.workspace_write`, and `Sandbox.full_access`
  map to app-server sandbox modes or turn sandbox policies.
- `thread_start`, `thread_resume`, and `thread_fork` accept `approval_mode`,
  `sandbox`, `cwd`, instructions, model, provider, personality, and service
  fields.
- `Thread.run` / `Thread.turn` accept turn overrides for `approval_mode`,
  `sandbox`, `cwd`, effort, model, output schema, personality, summary, and
  service tier.

The generated app-server protocol is deeper than the curated SDK:

- `ThreadStartParams` carries `approvalPolicy`, `approvalsReviewer`, `sandbox`,
  `cwd`, instructions, model, personality, service fields, and source fields.
- `TurnStartParams` carries `approvalPolicy`, `approvalsReviewer`, `cwd`,
  effort, input, model, `outputSchema`, personality, `sandboxPolicy`, summary,
  and `threadId`.
- `AskForApproval` supports `never`, `on-request`, `on-failure`, `untrusted`,
  and a granular approval object.
- `SandboxPolicy` supports `readOnly`, `workspaceWrite`, `dangerFullAccess`, and
  `externalSandbox`; workspace-write can carry `networkAccess` and
  `writableRoots`.
- Dynamic tools exist in protocol types: `DynamicToolSpec` has `name`,
  `description`, `inputSchema`, optional `namespace`, and optional
  `deferLoading`; dynamic tool calls appear as `dynamicToolCall` thread items.
- Client requests include `hooks/list`, `skills/extraRoots/set`,
  `mcpServer/tool/call`, `thread/goal/*`, `turn/start`, and `turn/interrupt`.
- Server notifications include `hook/started`, `hook/completed`,
  `item/autoApprovalReview/*`, `item/started`, `item/completed`, and
  `serverRequest/resolved`.

Codex app-server request handling is not a Claude-style callback option. It is
JSON-RPC server requests observed while reading the turn stream. The request
methods Yoke currently handles include command approval, file-change approval,
permissions approval, user-input requests, MCP elicitation, and dynamic tool
calls.

## What Yoke currently exposes

Current Yoke code already matches this split:

- `ClaudeOptions` has `permission_mode`, `allowed_tools`, `disallowed_tools`,
  `can_use_tool`, `request_handler`, `policy`, `hooks`, `agents`, and `raw`.
- `Hook` and `HookEvent` model Claude hook names, but callbacks are
  runtime-only because they are live Python callables.
- `CodexOptions` has `sandbox`, `approval`, `approvals_reviewer`, `network`,
  `writable_roots`, `collaboration`, `experimental_api`, `app_server`, and
  `raw`.
- `CodexAppServerOptions` has `policy`, runtime-only `request_handler`,
  `opt_out_notification_methods`, and `mcp_server_openai_form_elicitation`.
- `RequestPolicy` is the portable layer. It lowers to Claude permission results
  or Codex JSON-RPC responses without pretending the transports are the same.

## What Yoke should expose or document next

1. Document `tools` versus `allowed_tools` versus `disallowed_tools` for Claude.
   This is the most likely user mistake. `allowed_tools` is permission
   allowlisting, not availability.

2. Document `can_use_tool` versus `PreToolUse`. `can_use_tool` only sees
   permission prompts. `PreToolUse` can observe or gate every matching tool use.

3. Add a compact provider-native options table to the reference docs:
   Claude has `permission_mode`, tool rules, `can_use_tool`, hooks, and MCP
   tool approval. Codex has sandbox, approval policy, approval reviewer,
   network/writable roots, app-server request events, and app-server hook
   notifications.

4. Keep runtime callbacks out of folders. Claude hooks, Claude `can_use_tool`,
   Claude `request_handler`, and Codex app-server `request_handler` should stay
   runtime-only and visible through `runtime_options()`.

5. Do not add a portable `hooks=` abstraction yet. Claude hooks are executable
   callbacks with control outputs. Codex hooks are configured/listed/executed by
   app-server/plugin machinery and surfaced as notifications. A shared hook API
   would hide real differences.

6. Consider a small `ToolPolicy` or docs-only recipe before adding new code.
   The practical portable user need is usually “allow reads/searches, ask or
   deny shell/writes.” `RequestPolicy` already covers much of that. If a new API
   appears, it should compile to Claude permission rules/callbacks and Codex
   request responses, not to a fake shared hook layer.

7. For Codex dynamic tools, document them as app-server protocol pressure, not a
   stable Yoke public option yet. The generated protocol has `DynamicToolSpec`
   and dynamic tool call items, but the current public Codex Python SDK does not
   expose a simple high-level dynamic-tool registration method like Claude's
   `@tool` / SDK MCP server path.

## References read

- `claude-agent-sdk-python/src/claude_agent_sdk/types.py`
- `claude-agent-sdk-python/README.md`
- `openai-codex/sdk/typescript/src/threadOptions.ts`
- `openai-codex/sdk/typescript/src/events.ts`
- `openai-codex/sdk/typescript/src/items.ts`
- `openai-codex/sdk/python/src/openai_codex/_approval_mode.py`
- `openai-codex/sdk/python/src/openai_codex/_sandbox.py`
- `openai-codex/sdk/python/src/openai_codex/api.py`
- `openai-codex/sdk/python/src/openai_codex/generated/v2_all.py`
- `Yoke/docs/reference.md`
- `Yoke/src/yoke/options.py`
- `Yoke/src/yoke/providers/codex_app/events.py`
