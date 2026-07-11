# Event stream parity research - 2026-07-04

Scope: local code only. Sources inspected: Yoke, `/Users/rohan/Desktop/Projects/openai-codex`, and `/Users/rohan/Desktop/Projects/claude-agent-sdk-python`.

## 1. Provider-native event categories

### Codex app-server

Codex app-server exposes a JSON-RPC notification/request stream. The generated Python SDK protocol exports the main notification classes in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7549`, including:

- Turn lifecycle: `turn/started`, `turn/completed` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7955` and `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7963`.
- Item lifecycle: `item/started`, `item/completed` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7606` and `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7614`.
- Text/agent deltas: SDK stream examples branch on `item/agentMessage/delta` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/examples/03_turn_stream_events/async.py:36`.
- Plan/progress: `turn/plan/updated` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7597`.
- Patch/diff progress: `item/fileChange/patchUpdated` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7623`.
- Usage/rate limits: `thread/tokenUsage/updated` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7567`, plus `account/rateLimits/updated` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7633`.
- Goals/settings: `thread/goal/updated` and `thread/settings/updated` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7557` and `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7567`.
- Hooks/approvals: `hook/completed`, `item/autoApprovalReview/started`, and `item/autoApprovalReview/completed` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7588`, `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7972`, and `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7983`.
- Raw Responses items: `rawResponseItem/completed` represented by `RawResponseItemCompletedNotification` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/generated/v2_all.py:7932`.
- Global/app events: `app/list/updated`, `windowsSandbox/setupCompleted`, config warnings, skills changes, realtime events, model routing/verification/safety-buffer events, and thread status changes are emitted in app-server code paths such as `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/src/bespoke_event_handling.rs:182` and `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/src/bespoke_event_handling.rs:335`.
- Server requests: approval, user-input, permissions, MCP elicitation, and app/tool calls. Yoke's app-server helper already recognizes these in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/rpc.py:60`.

### Codex Python SDK

Codex Python SDK exposes the app-server protocol as typed `Notification` objects. The public docs say `TurnHandle.stream() -> Iterator[Notification]` / `AsyncIterator[Notification]` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/docs/api-reference.md:213` and `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/docs/api-reference.md:226`.

The SDK stream example handles only representative event methods: `turn/started`, `item/agentMessage/delta`, `item/completed`, and `turn/completed` in `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/examples/03_turn_stream_events/async.py:32`.

So Codex Python SDK is not a separate event taxonomy. It is the app-server event taxonomy surfaced as Python models.

### Claude Agent SDK Python

Claude Agent SDK exposes parsed message objects from the Claude Code stream. Main categories are defined and parsed in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py` and `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py`:

- User/assistant/result/system messages: `UserMessage`, `AssistantMessage`, `ResultMessage`, `SystemMessage` parsed in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:95`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:150`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:293`, and `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:210`.
- Content blocks: text, thinking, tool use, tool result, server tool use, advisor/server tool result in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:150`.
- Raw stream events: `StreamEvent` parsed from `type == "stream_event"` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:325`.
- Rate limit events: `RateLimitEvent` parsed from `type == "rate_limit_event"` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:336`.
- Background task lifecycle: `task_started`, `task_progress`, `task_notification`, and `task_updated` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:212`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:223`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:237`, and `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:248`.
- Hook lifecycle: hook events include `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`, `Notification`, `SubagentStart`, and `PermissionRequest` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py:190`.
- Permission/control requests: `can_use_tool`, `hook_callback`, `mcp_message`, `rewind_files`, `mcp_reconnect`, `mcp_toggle`, and `stop_task` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py:1999`.
- Result metadata: `permission_denials`, `deferred_tool_use`, `errors`, and `api_error_status` are parsed into `ResultMessage` in `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/message_parser.py:306`.

## 2. Current Yoke mapping

Yoke's normalized event vocabulary is in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/models.py:257`. Current kinds include text, tool lifecycle, request events, context usage, provider session, warning/error/done, hook, rate limit, goal updates, and a raw `stream_event` escape hatch.

Codex app-server mapping is relatively rich in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py`:

- `item/agentMessage/delta` -> `text_delta` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:155`.
- `item/plan/delta`, command output deltas, and file-change output deltas -> `tool_summary` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:169`.
- `turn/plan/updated` -> `tool_summary` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:186`.
- `thread/tokenUsage/updated` -> `context_usage` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:198`.
- `item/started` -> `tool_use`, `item/completed` -> `text` or `tool_result` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:212`.
- Goal updates/clears -> `goal_updated` / `goal_cleared` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:241`.
- Server requests -> `approval_request`, `user_input_request`, or `tool_request` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:372`.
- Collaboration items `collabToolCall` / `collabAgentToolCall` become `ToolKind.AGENT` plus `AgentCall` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:727`.

Codex Python SDK mapping is shallow. `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_sdk.py:235` streams SDK events through `sdk_event()`, and `sdk_event()` just sets `kind` to `event.method` with raw payload in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_sdk.py:512`.

Claude mapping is moderate-to-rich in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py`:

- `AssistantMessage` blocks -> `text`, `tool_use`, `tool_result`, plus `context_usage` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:999`.
- `ResultMessage` -> final `text`, `context_usage`, and `done` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:1425`.
- `SystemMessage` -> `provider_session` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:953`.
- `StreamEvent` -> raw `stream_event` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:963`.
- `HookEventMessage` -> `hook` with optional tool/agent attribution in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:1179`.
- `RateLimitEvent` -> `rate_limit` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:979`.
- `TaskStartedMessage`, `TaskProgressMessage`, and `TaskNotificationMessage` -> `tool_use`, `tool_summary`, and `tool_result` in `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:1158`, `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:1336`, and `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/claude.py:1360`.

## 3. Gaps and recommendations

1. Reuse the Codex app-server mapper for Codex Python SDK events.

   The Python SDK stream exposes the same app-server notification methods, but Yoke currently returns raw `Event(kind=event.method, raw=event)`. This misses normalized `text_delta`, `tool_use`, `tool_result`, usage, goals, request resolution, and agent-call fields. Recommendation: add a small adapter that converts SDK `Notification` objects to the same JSON-ish shape consumed by `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py`, then call `map_notification()`.

2. Add normalized lifecycle kinds or intentionally document raw fallback for lifecycle-only events.

   Yoke has `done` but no `turn_started`, `turn_completed`, `thread_started`, `thread_status`, `settings_updated`, `app_updated`, `skills_changed`, or `realtime_*` normalized kinds. That is acceptable for `Harness.run()` output, but not for apps that want a faithful provider-event UI. Recommendation: either add a small `lifecycle` event kind with `message`/`raw`, or keep provider method strings but document that those are outside the stable normalized core.

3. Add explicit review/approval-review events for Codex.

   Codex app-server has `item/autoApprovalReview/started` and `item/autoApprovalReview/completed`; Yoke currently does not map them in `map_notification()`. These are distinct from approval requests: they are provider-side review lifecycle. Recommendation: add `review_started` / `review_completed`, or map them to `tool_summary` with `ToolKind.UNKNOWN` and the review id/action in `tool_result`.

4. Add account-rate-limit mapping for Codex app-server.

   Yoke has `rate_limit` and Claude maps `RateLimitEvent`, but Codex app-server `account/rateLimits/updated` is not handled. Recommendation: map it to `rate_limit` and preserve the raw payload.

5. Add patch/diff progress mapping for Codex.

   The generated SDK has `item/fileChange/patchUpdated`; Yoke maps generic file-change output deltas but not patch-updated notifications. Recommendation: map patch updates to `tool_summary` or add a `file_change_delta` kind if UI needs structured diffs.

6. Preserve Claude thinking/server-tool blocks more explicitly.

   Claude parser supports `thinking`, `server_tool_use`, and `advisor_tool_result` blocks. Yoke currently maps text/tool-use/tool-result blocks but ignores thinking and server-tool-specific identity. Recommendation: map thinking to `tool_summary` or a new `thinking` kind, and map `ServerToolUseBlock` / `ServerToolResultBlock` to normal tool events with a `server_tool` marker in `raw` or `tool.summary`.

7. Map Claude `TaskUpdatedMessage`.

   Claude parser treats `task_updated` as a typed lifecycle message, but Yoke's `claude_events()` does not branch on `TaskUpdatedMessage`. Recommendation: map terminal `task_updated` patches to `tool_result` and non-terminal patches to `tool_summary`.

8. Surface Claude result errors and deferred tool use.

   `ResultMessage` carries `permission_denials`, `deferred_tool_use`, `errors`, and `api_error_status`, but Yoke `result_events()` only emits text, usage, and done. Recommendation: emit `error` when `is_error`, `errors`, or `api_error_status` is present; emit a `tool_request` or `tool_use`-like event for `deferred_tool_use` if Yoke wants resumable deferred tools.

9. Fix `RequestKind` if request subtypes are meant to be public.

   `/Users/rohan/Desktop/Projects/Yoke/src/yoke/providers/codex_app/events.py:385` returns `RequestKind.PERMISSION`, `RequestKind.USER_INPUT`, `RequestKind.TOOL`, and `RequestKind.UNKNOWN`, but `/Users/rohan/Desktop/Projects/Yoke/src/yoke/models.py:282` only defines `APPROVAL`. This looks like a real model mismatch. Recommendation: extend `RequestKind` or make `server_request_request_kind()` return strings.

10. Do not add provider-specific event classes to the core model yet.

    The current `Event.raw` escape hatch is doing useful work. The most valuable next step is not a large class hierarchy; it is parity mapping for the high-value missing classes above, while preserving raw provider payloads for consumers that need exact protocol details.
