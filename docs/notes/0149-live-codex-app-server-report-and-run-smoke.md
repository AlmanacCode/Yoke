# Live Codex app-server report and run smoke

Date: 2026-07-04

## Why this note exists

Yoke cannot treat "Codex support" as one flat capability. Codex exposes different surfaces, and the app-server surface currently has the richest shape for Yoke's goals: streaming activity, native collab-agent events, and thread-level goal methods. This note records the live command and output so future work keeps the surface distinction concrete.

## Command

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --capabilities --run-codex-app-server
```

## Result

```text
codex:codex_app_server: ok: Logged in using ChatGPT
  capabilities: codex:codex_app_server
    collab_agent_tools: native
      lowering: Codex app-server emits native collabAgentToolCall events such as spawnAgent; Yoke normalizes them into AgentCall event payloads.
    declared_subagents: compiled
      lowering: Yoke subagents compile into app-server developer instructions; native Codex collab-agent events remain provider-owned activity.
    goal: native
      lowering: Run goals can compile into instructions; session goal methods use app-server thread/goal JSON-RPC.
    mutable_goal: native
      lowering: Session.set_goal and clear_goal call app-server thread/goal methods.
    readable_goal: native
      lowering: Session.get_goal calls app-server thread/goal/get.
    skills: native
      lowering: Yoke wires skill roots into the app-server environment and can bundle inline skills as filesystem skill artifacts.
    workflow: emulated
      lowering: Yoke executes workflow steps as app-server turns; native collab agents are observed through events, not used as the workflow runtime.
codex_app_server run: succeeded: yoke-app-smoke
```

## Design implication

`provider="codex"` is not enough information for deep support. Yoke should keep modeling provider plus surface, because Codex app-server can support thread goal operations and rich event normalization that Codex SDK or CLI surfaces may not expose in the same way.

## Current Yoke stance

- `codex:app` is the preferred Codex surface when the caller asks for deep session goals, request handling, streaming event normalization, or app-server-native activity.
- Declared Yoke subagents remain portable Yoke configuration and compile into provider instructions/artifacts.
- Codex-native collab-agent activity remains provider-owned runtime behavior and is observed through normalized `AgentCall` events.
- Yoke workflows remain a portable runtime abstraction today. The app server runs each workflow step as a turn; it does not become Yoke's workflow engine.
