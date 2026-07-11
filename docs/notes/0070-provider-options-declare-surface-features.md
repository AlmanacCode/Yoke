# Provider options declare surface features

Date: 2026-07-04

Provider-specific options can imply provider-surface requirements.

Yoke now models Codex app-server `collaborationMode` as `Feature.COLLABORATION_MODE`. This is separate from `Feature.COLLAB_AGENT_TOOLS`: one means the surface accepts collaboration mode parameters, the other means the surface may emit collaboration-agent tool activity.

`CodexOptions.features()` returns `Feature.COLLABORATION_MODE` when typed `collaboration` is set or raw `collaboration_mode` / `collaborationMode` exists. `ProviderOptions.features()` combines provider-specific feature requirements, and `RunOptions`, `SessionOptions`, and `WorkflowOptions` include those provider option features in their own `features(...)` results.

This lets Yoke route correctly:

- a run/session/workflow with Codex collaboration mode selects or validates `codex_app_server`;
- raw provider options still work for fields Yoke has not fully typed;
- provider-specific options own their own capability pressure instead of hiding it inside adapters.
