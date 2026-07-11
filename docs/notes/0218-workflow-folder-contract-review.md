# 0218 Workflow folder contract review

Date: 2026-07-04

Yoke should keep the current folder-first `Workflow` shape, but tighten the contract around identity, replay, and event visibility.

## Copy

- Copy Eve's path-derived identity rule. Folder workflow names and step names should come from `workflows/<name>/` and `*.md`, with metadata allowed only when it matches the path. Yoke already does this for workflows and steps.
- Copy Eve's authored-slot model where it helps: `skills/`, `subagents/`, and `workflows/` are separate slots, and declared subagents are isolated agent roots. This matches Yoke's current `Agent` shape.
- Copy the two-handle lesson from Eve and Codex. Keep run identity separate from resume/continuation identity: `WorkflowRun.run_id` is for inspection/traces, while `WorkflowOptions.resume` or provider-native `resumeFromRunId` is a resume handle.
- Copy Claude Python's small store protocol style for replay. Yoke's `WorkflowReplay.get/put` seam is the right level: append/load/store behavior should be provider-neutral and not byte-for-byte tied to one provider transcript format.
- Copy event/tracing pressure from Eve and Codex. Workflow output should expose parent-visible control events and child run/traces, not hide subagent work inside a final string.

## Do not copy

- Do not copy Eve's durable Workflow runtime into Yoke. Eve owns a whole durable session engine; Yoke should stay an SDK-level adapter/orchestration layer.
- Do not make Codex goals look like Yoke workflows. Codex goals are thread-scoped state plus streamed turns, not a portable workflow DSL.
- Do not make Codex skills/hooks a folder contract in Yoke until Yoke has a provider-neutral story. Codex discovers skills and hooks from app-server/runtime config, not from Yoke's agent folder.
- Do not copy Claude Python hook output names directly into Yoke's public model. Claude has Python keyword workarounds like `async_`/`continue_` and CLI-specific hook event names.
- Do not treat provider-native Workflow as common. Claude TypeScript has a native Workflow input shape; Codex app-server does not expose an equivalent workflow primitive in the inspected docs/source.

## Naming/API pressure

- `Workflow` can stay as the single public word, but docs should call out the three bodies: Python program, portable step DAG, provider-native input.
- `workflow.py` folder programs are good, but the callable contract should remain `main(ctx)` and should not serialize Python handlers into folder metadata.
- `resume_from_run_id` should remain provider-native input; Yoke's own replay option should stay named `resume` or `run_id`-oriented to avoid implying provider resume semantics.
- If Yoke adds hooks, prefer `hooks/` as a folder slot and `EventKind` names over provider names like `PreToolUse` or Codex JSON-RPC method names.
- Subagent naming should stay bare and path-derived. Add collision checks before making subagents/tools/workflows share a visible runtime namespace.

## References

- Current Yoke folder loader: `src/yoke/loader.py:23-54`, `src/yoke/loader.py:177-291`.
- Current Yoke workflow model: `src/yoke/models.py:633-774`, `src/yoke/models.py:790-804`.
- Current Yoke orchestration split: `src/yoke/workflows.py:24-39`, `src/yoke/workflows.py:105-126`.
- Current Yoke replay seam: `src/yoke/replay.py:10-18`.
- Current Yoke design note: `docs/notes/0217-flow-is-claude-style-workflow-functionality.md:34-44`, `docs/notes/0217-flow-is-claude-style-workflow-functionality.md:96-108`, `docs/notes/0217-flow-is-claude-style-workflow-functionality.md:133-145`.
- Eve path/slot contract: `/Users/rohan/Desktop/Projects/eve/docs/reference/project-layout.md:6-19`, `/Users/rohan/Desktop/Projects/eve/docs/reference/project-layout.md:49-72`, `/Users/rohan/Desktop/Projects/eve/docs/reference/project-layout.md:91-97`.
- Eve durability/session handles/events: `/Users/rohan/Desktop/Projects/eve/docs/concepts/execution-model-and-durability.md:10-18`, `/Users/rohan/Desktop/Projects/eve/docs/concepts/execution-model-and-durability.md:41-51`, `/Users/rohan/Desktop/Projects/eve/docs/concepts/sessions-runs-and-streaming.md:8-15`, `/Users/rohan/Desktop/Projects/eve/docs/concepts/sessions-runs-and-streaming.md:35-58`.
- Eve subagents/skills/hooks: `/Users/rohan/Desktop/Projects/eve/docs/subagents.mdx:54-112`, `/Users/rohan/Desktop/Projects/eve/docs/skills.mdx:6-18`, `/Users/rohan/Desktop/Projects/eve/docs/guides/hooks.md:6-29`, `/Users/rohan/Desktop/Projects/eve/docs/guides/hooks.md:74-90`.
- Codex app-server sessions/goals/skills/hooks/events: `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:64-81`, `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:140-156`, `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:209-212`, `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:1351-1378`, `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:1607-1643`, `/Users/rohan/Desktop/Projects/openai-codex/codex-rs/app-server/README.md:1719-1725`.
- Codex Python SDK thread API and goal routing: `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/docs/api-reference.md:53-74`, `/Users/rohan/Desktop/Projects/openai-codex/sdk/python/src/openai_codex/_goal.py:36-87`.
- Claude Python agents/hooks/session store: `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py:82-101`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py:258-270`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py:411-490`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/client.py:119-132`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/client.py:216-251`, `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/testing/session_store_conformance.py:81-125`.
