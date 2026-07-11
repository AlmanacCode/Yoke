# Native workflow and goal reference check

2026-07-04

Scope: local clones only. Checked Claude Agent SDK Python, OpenAI Codex, and Eve for native `Goal`, `Workflow`, `Agent`, and `Session` surfaces relevant to Yoke.

## Short conclusion

Yoke should model `Goal`, `Workflow`, `Agent`, and `Session` as provider-neutral concepts, but only some are native in each reference:

| Concept | Claude Agent SDK Python | OpenAI Codex app-server | Eve |
| --- | --- | --- | --- |
| `Goal` | Not a public SDK concept. Only `<goal>` appears as a transcript/system prompt marker skipped by session listing. | Native thread goal API. | No native goal surface found. |
| `Workflow` | Not a durable/public concept. Used as ordinary wording and as a nested subagent transcript path segment. | Not a first-class workflow API. Threads/turns/items plus plan updates are native. | Native durability model: every turn runs as a Workflow SDK workflow. |
| `Agent` | Native `AgentDefinition` for custom subagents. | The product is an agent, but app-server primitives are thread/turn/item. | Native filesystem agent and subagent model via `defineAgent`. |
| `Session` | Native session id, resume/continue/fork, transcript store. | Native user-facing primitive is `Thread`; `sessionId` is live thread-tree/root metadata. | Native durable HTTP session with `sessionId`/`runId` and `continuationToken`. |

## Claude Agent SDK Python

Relevant files:

- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py`
- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/client.py`
- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/_internal/sessions.py`
- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/tests/test_session_import.py`

Native surfaces:

- `AgentDefinition` is a dataclass with `description`, `prompt`, tool limits, model, skills, MCP servers, `initialPrompt`, `maxTurns`, `background`, `effort`, and `permissionMode`.
- `ClaudeAgentOptions.agents` maps names to `AgentDefinition` and makes custom subagents invokable through the Agent tool.
- `ClaudeAgentOptions` has session controls: `continue_conversation`, `resume`, `session_id`, `fork_session`, `session_store`, and `session_store_flush`.
- `SessionStore` is a transcript mirror/resume adapter keyed by `project_key`, `session_id`, and optional `subpath` for subagents.

Workflow/goal findings:

- No public `Workflow` type or workflow lifecycle API showed up in the SDK surface.
- `client.py` says `receive_response()` is useful for "single-response workflows", but that is plain English, not a native entity.
- `_internal/sessions.py` recognizes nested subagent transcript paths such as `subagents/workflows/<runId>/agent-<id>`.
- `_internal/sessions.py` skips `<goal>` when deriving the first meaningful user prompt, but there is no public `Goal` model or goal API in this clone.

Yoke conclusion:

- Mirror Claude for `Agent` and `Session` where Yoke targets Claude.
- Do not pretend Claude has native `Goal` or durable `Workflow` concepts. Treat Yoke goals/workflows as Yoke-owned metadata/orchestration when running Claude.

## OpenAI Codex app-server

Relevant files:

- `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md`
- `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/src/request_processors/thread_goal_processor.rs`
- `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/tests/suite/v2/thread_resume.rs`
- `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/Cargo.toml`

Native surfaces:

- App-server core primitives are `Thread`, `Turn`, and `Item`.
- `thread/start`, `thread/resume`, and `thread/fork` create or continue conversations.
- `turn/start` drives a conversation; turn notifications stream item lifecycle and `turn/plan/updated`.
- The README calls out `thread.sessionId` for the current live session tree root, but the API surface is still thread-first.

Goal surface:

- `thread/goal/set` creates or updates the single persisted goal for a materialized thread.
- `thread/goal/get` returns the goal or `null`.
- `thread/goal/clear` removes the goal and emits `thread/goal/cleared` when state changes.
- `thread/goal/updated` includes the full current goal.
- `ThreadGoal` maps fields: `threadId`, `objective`, `status`, `tokenBudget`, `tokensUsed`, `timeUsedSeconds`, `createdAt`, `updatedAt`.
- Statuses mapped in app-server are `active`, `paused`, `blocked`, `usageLimited`, `budgetLimited`, and `complete`.
- Goals are feature-gated. `thread_goal_processor.rs` returns `goals feature is disabled` when `Feature::Goals` is off.
- Ephemeral threads do not support goals.

Workflow findings:

- No first-class `Workflow` API appears in the app-server protocol surface read here.
- `turn/plan/updated` is a plan event, not a workflow abstraction.
- `Cargo.toml` references `codex-rs/ext/goal`, and app-server imports `codex_goal_extension`, but the `codex-rs/ext/goal` source directory was not present in this local checkout. The processor and tests are the concrete readable local evidence.

Yoke conclusion:

- Mirror Codex most closely for `Goal`: thread/session-attached, persisted, optional token budget, usage accounting, clear/update notifications, and stopped statuses.
- For Codex, map Yoke `Session` to `Thread` externally, while preserving Codex's `sessionId` as provider metadata.
- Do not map Codex plan updates to Yoke `Workflow` unless Yoke explicitly defines workflow as a higher-level orchestration concept.

## Eve

Relevant files:

- `/Users/rohan/Desktop/Projects/eve/docs/concepts/execution-model-and-durability.md`
- `/Users/rohan/Desktop/Projects/eve/docs/concepts/sessions-runs-and-streaming.md`
- `/Users/rohan/Desktop/Projects/eve/docs/agent-config.md`
- `/Users/rohan/Desktop/Projects/eve/docs/subagents.mdx`
- `/Users/rohan/Desktop/Projects/eve/packages/eve/src/shared/agent-definition.ts`
- `/Users/rohan/Desktop/Projects/eve/packages/eve/src/runtime/types.ts`

Native surfaces:

- `defineAgent` is the authored agent config surface.
- Eve agents are filesystem-first under `agent/`; declared subagents live under `agent/subagents/<id>/` and use `defineAgent`.
- Eve sessions are durable. The docs define `session`, `turn`, and `step`.
- Every turn runs as a durable Workflow SDK workflow.
- The stable HTTP API exposes `POST /eve/v1/session`, `GET /eve/v1/session/:sessionId/stream`, `sessionId`/`runId`, and `continuationToken`.
- `experimental.workflow.world` selects the Workflow world package backing session state, queues, hooks, and streams.
- Eve also has an optional root-only `Workflow` orchestration tool; `workflowEnabled` records whether the author opted into it.

Goal findings:

- Targeted local searches found no `Goal`/`goal` docs or runtime surface in the relevant Eve docs/runtime files.

Yoke conclusion:

- Mirror Eve for durable `Workflow` semantics if Yoke wants workflows to mean resumable, checkpointed execution.
- Mirror Eve's split between `continuationToken` and `sessionId`/`runId`: one handle resumes input, one handle streams/inspects.
- Do not invent a native Eve `Goal`; represent goals as Yoke metadata if needed.

## Provider-neutral recommendation for Yoke

- `Session`: make this the stable Yoke conversation/run container. Store provider handles separately: Claude `session_id`, Codex `threadId` plus `sessionId`, Eve `sessionId`/`runId` plus `continuationToken`.
- `Agent`: support both authored agents and subagents. Claude and Eve have concrete subagent definitions; Codex app-server is mostly thread/turn oriented, so avoid forcing a Codex-native agent definition shape.
- `Goal`: make this optional provider capability plus Yoke-owned metadata. Codex is the native reference. Claude and Eve should report unsupported/native-absent rather than fake parity.
- `Workflow`: make this Yoke-owned orchestration unless running on Eve-like durable workflow backends. Eve is the native reference. Claude and Codex should not be described as having native workflows based on local evidence.
