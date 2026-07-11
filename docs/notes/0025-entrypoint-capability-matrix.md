# Entrypoint capability matrix must shape Yoke

Yoke cannot model "Claude" or "Codex" as a single flat provider capability set. Each provider exposes several entrypoints, and the entrypoint determines which features are native, compiled, emulated, or unavailable.

Codex is the clearest example. The CLI is useful for simple one-shot and resumable execution, but the app-server surface appears to expose the richer runtime: streaming notifications, thread lifecycle, skill roots, native goal read/write/clear, and lower-level session control. Yoke should therefore prefer `codex_app_server` when callers ask for features that require those capabilities, and it should make downgrades explicit when the caller chooses `codex_cli`.

Claude has a similar but different split. The Python Agent SDK exposes programmatic agents, subagents, hooks, tool surfaces, and local plugin integration. Claude Code CLI/plugin behavior is not automatically equivalent to the Python SDK. Yoke should track Claude SDK, Claude CLI, and any future Claude app/server surfaces separately instead of assuming feature parity.

This means every Yoke feature needs an entrypoint row, not just a provider row:

| Feature | Claude SDK | Claude CLI | Codex CLI | Codex app-server |
| --- | --- | --- | --- | --- |
| one-shot run | native | research required | native | native |
| live session | native | research required | compiled/resumable | native |
| streaming events | native-ish through SDK iteration | research required | limited JSON events | native notifications |
| folder skills | native via plugin roots or compiled | research required | compiled prompt | native extra skill roots |
| programmatic subagents | native | research required | compiled prompt | likely compiled until app-server exposes agent definitions |
| mutable goals | unsupported/compiled | research required | unsupported/compiled | native |
| readable goals | unsupported | research required | unsupported | native |
| workflow execution | emulated by Yoke | emulated by Yoke when supported | emulated by Yoke | emulated by Yoke |

Vocabulary cleanup from the 2026-07-04 capability slice:

- `Feature.GOAL` means the surface can receive a goal for a run or session.
- `Feature.MUTABLE_GOAL` means the surface can set or clear goal state after a session exists.
- `Feature.READABLE_GOAL` means the surface can inspect provider goal state.
- `Feature.WORKFLOW` is `emulated` for current surfaces because Yoke orchestrates multiple turns; providers do not supply a portable workflow primitive.
- Codex app-server native collab-agent activity is not the same as user-declared Yoke subagents. Do not mark Yoke subagents native on that basis.
- `Feature.COLLAB_AGENT_TOOLS` means the provider emits native agent-tool activity, such as Codex app-server `collabAgentToolCall` items. It is separate from `Feature.DECLARED_SUBAGENTS`.

The SDK contract should expose this honestly. A caller should be able to ask `harness.capabilities` and see support per surface, and Yoke should choose the richest default surface only when that does not surprise the caller operationally. Long-running app-server sessions change process and lifecycle behavior, so auto-upgrading from CLI to app-server should probably require an explicit policy.

Open research items:

- Confirm the current Codex app-server protocol surface from the source tree and docs, especially around streaming, approval events, goal events, skill roots, and session persistence.
- Confirm the current Codex CLI JSON event contract and whether it exposes enough structured tool/status data for reliable Yoke normalization.
- Confirm Claude Python Agent SDK support for subagents, hooks, plugins, output schemas, session continuation, and streaming event shapes.
- Confirm what Claude CLI supports that the Python SDK does not, and vice versa.
- Keep Yoke's public API small while preserving escape hatches for provider-specific options.
