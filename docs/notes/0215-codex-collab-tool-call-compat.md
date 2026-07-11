# 0215 Codex app-server collab tool call compatibility

Date: 2026-07-04

Current Codex app-server docs use `collabToolCall` for provider-native collaboration/subagent tool activity. Older Yoke notes and tests used `collabAgentToolCall`.

Yoke now accepts both shapes:

- `collabToolCall` is the current app-server item type.
- `collabAgentToolCall` remains supported as a legacy item type.
- `receiverThreadId` maps to `AgentCall.receiver_thread_ids` as a single-item tuple.
- legacy `receiverThreadIds` remains supported.
- `agentStatus` maps to `AgentCall.states`; legacy `agentsStates` remains supported.

This keeps Codex app-server native collaboration activity separate from `Agent.subagents`. Yoke-declared subagents still compile into Codex instructions or provider files unless a surface exposes a direct declared-subagent API.

Sources:

- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/subagents

## Live smoke follow-up

`--run-codex-app-collab` now exercises provider-native Codex app-server collaboration activity through Yoke.

The first live attempt without `CodexOptions(experimental_api=True)` reached app-server readiness and failed at `turn/start`:

```text
Codex app-server turn/start: turn/start.collaborationMode requires experimentalApi capability
```

The smoke now enables `experimental_api=True` for this specific collaboration-mode run.

Successful live command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-collab
```

Result:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server collab: succeeded: agent_events=4 output='yoke-codex-collab-subagent-smoke'
```

Yoke implication: keep `Feature.COLLABORATION_MODE` separate from `Feature.EXPERIMENTAL_API` in the model, but any app-server helper or smoke that sends `collaborationMode` must opt into experimental API until the provider no longer requires it.
