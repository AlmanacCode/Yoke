# Codex declared subagents

Yoke-declared subagents now compile into Codex prompt context.

The distinction matters:

- Claude Python SDK can receive Yoke subagents through Claude `AgentDefinition`.
- Codex CLI does not expose a portable subagent-definition API through `codex exec`.
- Codex app-server exposes native collab-agent activity in events, but that is not the same as accepting user-declared Yoke subagents.

The current Yoke behavior is therefore:

- `Feature.DECLARED_SUBAGENTS` is `compiled` for Codex CLI.
- `Feature.DECLARED_SUBAGENTS` is `compiled` for Codex app-server.
- `Feature.INLINE_SUBAGENTS` stays `unsupported` for Codex surfaces until Yoke owns a real delegation story or discovers a native provider contract.
- `Feature.COLLAB_AGENT_TOOLS` is `native` for Codex app-server because app-server emits `collabAgentToolCall` items for tools such as `spawnAgent`, `sendInput`, `resumeAgent`, `wait`, and `closeAgent`.

Compiled subagents are rendered as named specialist instructions. The prompt text explicitly says they are not native delegated processes on that surface. This prevents the SDK from promising parallel workers or separate context windows that the selected Codex entrypoint does not provide.

This slice also fixed Codex CLI prompt assembly to include root `Agent.instructions`. Before this, Codex app-server received developer instructions at thread start, while Codex CLI only received skills, goals, and the user request.

Additional app-server research on 2026-07-04:

- `thread/start` accepts `developerInstructions`, `baseInstructions`, `model`, `cwd`, permissions, sandbox, and thread source fields. It does not expose an `agents` or `subagents` declaration map.
- `turn/start` accepts `collaborationMode` as a turn/thread settings override. `CollaborationMode` contains `mode` and `settings`, and settings contain `developer_instructions`, `model`, and `reasoning_effort`.
- App-server thread objects include `parentThreadId`, `agentNickname`, and `agentRole` for AgentControl-spawned sub-agent threads.
- App-server turn items include `collabAgentToolCall` records with sender/receiver thread ids, prompt, model, reasoning effort, and tool names.
- App-server tests show spawned agents are produced by model function calls in namespaces such as `multi_agent_v1` and `collaboration`, not by client-declared agent definitions.

Yoke now normalizes Codex app-server `collabAgentToolCall` items as `ToolKind.AGENT` events while continuing to compile Yoke-declared subagents into instructions.

Yoke also exposes app-server collaboration mode through typed Codex provider options:

```python
from yoke import CodexOptions, Collaboration, CollaborationSettings, ProviderOptions, RunOptions

options = RunOptions(
    provider=ProviderOptions(
        codex=CodexOptions(
            collaboration=Collaboration(
                mode="plan",
                settings=CollaborationSettings(
                    developer_instructions=None,
                    model="gpt-5.4-mini",
                    reasoning_effort="medium",
                ),
            )
        )
    )
)
```

The app-server adapter forwards this as `collaborationMode` on `turn/start`. `developer_instructions=None` is preserved because app-server uses that explicit null to mean "use built-in instructions for the selected collaboration mode." `settings.model` is required by app-server when `collaborationMode` is present. Yoke still accepts raw dict options with either `collaboration_mode` or `collaborationMode` for app-server fields it has not modeled yet.

Verification:

- `tests/test_codex_subagents.py` checks Codex CLI prompt compilation.
- `tests/test_codex_subagents.py` checks Codex app-server developer instruction compilation.
- `tests/test_capabilities.py` checks Codex declared subagent support is `compiled`, not `native`.
- `tests/test_codex_app_events.py` checks Codex app-server collab agent tool calls normalize as `ToolKind.AGENT`.
- `tests/test_codex_app_server_params.py` checks typed and raw collaboration mode provider options flow into `turn/start` params.
- Live smoke on 2026-07-04 used `gpt-5.4-mini` and returned `yoke-collab-ok` with normal app-server warning, tool, text, usage, and done events.

Open research:

- Watch whether Codex app-server adds a native way to declare subagents beyond observing collab-agent events and setting collaboration mode.
- Check whether future Codex SDK surfaces expose explicit agent graph definitions.
- If native support appears, promote only that entrypoint from `compiled` to `native`.
