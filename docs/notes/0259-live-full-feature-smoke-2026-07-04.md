# 0259 - Live full-feature smoke pass

Date: 2026-07-04

## Summary

This pass ran real provider smokes for Yoke's highest-risk primitives. The tests
used live local authentication and real provider SDK/app-server turns, not fake
adapters.

## Readiness

Command:

```bash
uv run --with openai-codex --with claude-agent-sdk python scripts/smoke_harnesses.py --json --capabilities
```

Results:

- `codex:codex_cli` available: logged in using ChatGPT.
- `codex:codex_app_server` available: logged in using ChatGPT.
- `codex:codex_python_sdk` available: `openai_codex` available.
- `claude:claude_python_sdk` available: Claude authenticated via claude.ai.

## Codex app-server live suite

Command:

```bash
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server --run-codex-app-stream --run-codex-app-skills --run-codex-app-collab --run-codex-app-workflow --run-codex-app-request --run-codex-app-goal --run-codex-app-goal-loop --run-codex-app-rename --run-codex-app-fork
```

Results:

- One-shot run passed: output contained `yoke-app-smoke`.
- Stream passed: 40 events, including provider session, tool events, text deltas,
  usage, rate limit, and done; output contained `yoke-stream-smoke`.
- Folder skill smoke passed: output contained `yoke-codex-skill-smoke`.
- Collaboration/subagent smoke passed: 4 agent events; output contained
  `yoke-codex-collab-subagent-smoke`.
- Folder-first workflow smoke passed: first and second runs succeeded, replay was
  cached, one workflow record was written, and output contained
  `yoke-codex-workflow-smoke`.
- Request-event smoke passed: one app-server request, one handler call, output
  contained a random `yoke-codex-request-smoke-*` marker, and the approved smoke
  command ran.
- Native goal set/read/clear passed: initial and updated goals read back, then
  clear returned `None`.
- Goal-loop handle passed: returned a provider session handle with
  `auto_continues=True`.
- Rename passed: title read back as `Yoke smoke rename`.
- Fork passed: source and fork thread ids were distinct provider ids.

## Claude Python SDK live suite

Command:

```bash
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude --run-claude-hooks --run-claude-permissions --run-claude-skills --run-claude-subagents --run-claude-workflow --run-claude-fork
```

Results:

- One-shot run passed: output contained `yoke-claude-smoke`.
- Hook smoke passed: 6 hook events and 4 tool events; output contained
  `yoke-claude-hooks-smoke`.
- Permission callback smoke passed: one callback fired; output contained a
  random `yoke-claude-permission-smoke-*` marker.
- Folder skill smoke passed: output contained `yoke-claude-skill-smoke`.
- Declared subagent smoke passed: 2 agent events; output contained
  `yoke-claude-subagent-smoke`.
- Folder-first workflow smoke passed: first and second runs succeeded, replay was
  cached, one workflow record was written, and output contained
  `yoke-claude-workflow-smoke`.
- Fork passed: source and fork provider session ids were distinct.

## Codex Python SDK live suite

Command:

```bash
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk --run-codex-sdk-stream --run-codex-sdk-fork
```

Results:

- One-shot run passed: output contained `yoke-sdk-smoke`.
- Stream transport passed: 25 events were received, including tool activity and
  usage. The smoke intentionally does not require final text for this surface
  because the current SDK stream does not expose final assistant text through
  the same event contract as app-server.
- Fork passed: source and fork provider thread ids were distinct.

## Current meaning

Yoke's core v1 primitives are now live-smoked on this machine for the two main
product surfaces:

- Codex app-server: one-shot, streaming, folder skills, collaboration/subagent
  events, folder-first workflows, request events, native goals, goal loops,
  rename, and fork.
- Claude Python SDK: one-shot, hooks, permission callback, folder skills,
  declared subagents, folder-first workflows, and fork.
- Codex Python SDK: one-shot, streaming transport, and fork.

This is stronger evidence than the unit suite. Remaining live gaps are narrower:
model listing behavior across accounts, provider-native Claude TypeScript
workflow execution, public package install from an index, and downstream
`../usealmanac` integration.
