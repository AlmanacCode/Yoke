# Workflow and goal surface refresh

Date: 2026-07-04

This slice refreshed the workflow/goal model against current provider docs and the existing Yoke implementation.

## Current provider evidence

Claude Agent SDK Python exposes one-off `query()` and reusable `ClaudeSDKClient` sessions. The Python surface is strong for sessions, hooks, permissions, subagents, skills, MCP, structured outputs, and file operations, but it does not expose the Claude TypeScript SDK's native `Workflow` tool.

Claude Agent SDK TypeScript documents a `Workflow` tool. The tool runs a dynamic workflow script that can orchestrate many subagents in the background and return one consolidated result. Its input accepts inline `script`, named workflow `name`, `scriptPath`, `args`, and `resumeFromRunId`. The script form uses helpers such as `agent()`, `parallel()`, `pipeline()`, and `phase()`.

Codex docs use "workflows" mostly as usage patterns, automations, subagent workflows, or external orchestration through the OpenAI Agents SDK plus Codex MCP. Codex app-server is the deep product integration surface for auth, conversation history, approvals, and streamed agent events. The Codex SDK is the recommended automation/CI surface and controls local app-server behavior.

Codex `/goal` is a durable objective loop that can continue across turns until a verifiable stopping condition is met. Provider docs emphasize the goal text as both starting prompt and completion criteria. That is different from Yoke's compiled goal context for one-shot runs.

## Yoke design conclusion

Yoke should keep two workflow modes clear:

- Portable step workflows: `Workflow(steps=...)` run as Yoke-owned DAG orchestration over provider turns. This is the default because it works on runnable Python adapters.
- Native script workflows: `Workflow(script=...)` require a provider-native workflow primitive. Today that is tracked for Claude TypeScript SDK, not run by Yoke's Python adapter.

Yoke should keep three goal ideas separate:

- `Goal` as run/session context: compiled or native input to a bounded turn/session.
- native readable/mutable thread goals: provider state exposed through session methods, currently Codex app-server.
- native goal loops: provider-owned continuation behavior such as Codex `/goal`; this can outlive the normal "one run" intuition and must stay explicitly reported through surface status.

## Code/docs changes

- Fixed stale workflow feature recipes in `src/yoke/surfaces.py` from the old imagined `harness.workflow(...).run()` shape to the actual `await harness.workflow(workflow, prompt)` API.
- Added tests proving `WorkflowOptions(native=True)` plans to the tracked Claude TypeScript SDK surface when non-runnable surfaces are allowed.
- Added tests proving the same native workflow request fails when the caller requires a runnable Python Yoke adapter.

## Sources refreshed

- https://code.claude.com/docs/en/agent-sdk/python
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/sdk
- https://developers.openai.com/codex/workflows
- https://developers.openai.com/codex/use-cases/follow-goals
- https://developers.openai.com/codex/subagents

## Verification

In `/Users/rohan/Desktop/Projects/Yoke`:

```bash
PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_workflows.py tests/test_readiness.py
PYTHONPATH=src uv run pytest
uv run ruff check .
```

passed. The full pytest run reported 249 passing tests.
