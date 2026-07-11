# Remaining feature risk inventory

Date: 2026-07-04

Scope: targeted sidecar inventory for the product goal: provider-neutral Python SDK for Claude/Codex with agents, skills, subagents, workflows, goals, sessions, events, options, sync/async, folder-first and SDK-first use. Sources checked: README, recent notes 0223/0225/0231/0232/0235/0236/0237, provider-surface/event research, source module map, targeted source/test searches.

## What looks solid

- Public API shape is broad and intentional: `Agent`, `Harness`, `Session`, `Workflow`, `Goal`, `RunOptions`, `SessionOptions`, provider options, capability reports, status reports, folder save/load, bundles, and sync twins are exported from `yoke.__init__`.
- Capability planning is surface-level, not provider-level. Tests cover exact surfaces, aliases, v1 defaults, `require(...)`, option-driven features, agent-driven features, and `Plan.reports` lowering rows.
- Agent shape participates in planning. Recent notes/tests cover root goals, skills, declared subagents, workflows, recursive subagent features, and recursive inline skill artifacts.
- Folder-first authoring has real coverage. Tests cover agent save/load, scalar/rich goals, path-backed skills, workflow directories, native/script workflow folders, path-derived names, and overwrite safety.
- Event normalization is no longer just theoretical. Codex app-server maps text/tool/goal/request/rate-limit/review/patch/collab events, Codex Python SDK reuses the app-server mapper for known notifications, and Claude maps tool/thinking/server-tool/task/hook/result-pressure events.
- Session APIs have a clear public model: run/stream/start/close, sync context managers, interrupt, compact, rename/tag, fork, history listing/reading, and provider-specific limits are tested at the port level.

## Top 5 remaining gaps

1. Runnable surface parity is uneven. Codex app-server and Claude Python SDK are the deepest live targets; Codex Python SDK is improving but still has unsupported readable/mutable goals and goal-loop handling. TypeScript SDK surfaces are modeled as conceptual surfaces, not runnable adapters.
2. Native workflow semantics remain the biggest completion risk. Portable Yoke workflows are emulated, but provider-native workflow support is mostly capability/reporting shape. The Claude adapter explicitly rejects native workflow execution, and Codex surfaces should not be implied to have native workflow DSLs.
3. Goal APIs need a final product boundary pass. Codex app-server has native readable/mutable thread goal state; Claude has compiled goal context plus slash-command goal-loop behavior; Codex Python SDK currently lacks readable/mutable goals. The public API must keep those distinctions obvious.
4. SDK-first completion needs live proof, not just fake-module tests. Tests exercise Codex SDK one-shot/session/fork/interrupt/login paths with fakes, but the product promise needs an install/runtime smoke proving the published `openai-codex` package and Claude SDK still match the adapters.
5. Docs are close but high-churn. README already covers many advanced surfaces, but notes show docs have repeatedly lagged code around plan explainability, goal-loop semantics, workflow meaning, and provider-specific options. This is a product risk because Yoke's value is honest lowering, not just working calls.

## Concrete next implementation slices

1. Native workflow boundary slice: decide whether v1 ships only portable workflows for runnable Python surfaces, or adds one real native workflow adapter. Then make `WorkflowOptions(native=True)` either execute on that exact surface or fail with a capability/report-backed message.
2. Goal/session parity slice: finish the support matrix and examples for `get_goal`, `set_goal`, `clear_goal`, `goal_loop`, `inherit_goal`, session resume, interrupt, fork, compact, rename, and tag across Codex app-server, Codex SDK, Codex CLI, and Claude SDK.
3. SDK-first live adapter slice: run and harden live install smokes for `yoke[codex]` and `yoke[claude]`, including one-shot, stream, structured output, session start/send/close, interrupt where supported, fork where supported, and login start flows where safe.
4. Folder/bundle integrity slice: prove one recursive folder with main agent, subagent, skill, workflow, goal, and provider options can round-trip through `Agent.save`, `Agent.from_folder`, `agent.bundle(provider=...)`, and then be used by the chosen provider surface.
5. Event/control parity slice: freeze the stable normalized event contract and mark everything else as `stream_event` with raw payload. Add focused fixtures for lifecycle, review, request, permission, subagent, usage, rate-limit, and provider-session events on Claude and Codex.

## Tests and smokes that would prove completion

- Unit gate: `PYTHONPATH=src uv run pytest tests/test_public_api.py tests/test_capabilities.py tests/test_folders.py tests/test_workflows.py tests/test_goals.py tests/test_sessions.py tests/test_history.py tests/test_events.py tests/test_codex_app_events.py tests/test_codex_python_sdk.py tests/test_claude_events.py tests/test_smoke_harnesses.py`.
- Style gate: `PYTHONPATH=src uv run ruff check src tests scripts`.
- Live Codex app-server smoke: readiness, one-shot run, stream, request policy callback, readable/mutable goal, session resume, interrupt, fork, compact, rename, model list, and event capture for collab/tool/goal/rate-limit-like payloads.
- Live Codex Python SDK smoke: package import, config uses local `codex`, one-shot structured output, stream events through the neutral mapper, session start/send/close, interrupt active streamed turn, fork thread, and login start flows without leaking clients.
- Live Claude SDK smoke: readiness, one-shot structured output, stream, session resume, interrupt, fork if available, slash-command `goal_loop`, request callback, hooks/task events, subagent and skill lowering.
- Folder-first smoke: create one temp agent folder with recursive subagent/skill/workflow/goal/options, load it, bundle it for Claude and Codex, inspect expected provider files, and run a small prompt on the v1 default surfaces.
