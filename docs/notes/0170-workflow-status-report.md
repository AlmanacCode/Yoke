# Workflow status report

Yoke now exposes `Status.workflow` so callers can distinguish portable Yoke
workflows from provider-native workflow primitives.

The report has:

- `mode`: `yoke_portable`, `provider_native`, `unsupported`, or `unknown`.
- `portable`: support for `Feature.WORKFLOW`.
- `native`: support for `Feature.NATIVE_WORKFLOW`.
- `background`: true when the native provider primitive runs as background
  orchestration.

This mirrors the goal split. A portable Yoke workflow is a dependency DAG over
provider turns. It works across Codex and Claude surfaces that can take turns.
A provider-native workflow is different. Claude TypeScript Agent SDK documents
the `Workflow` tool as an async-launched dynamic workflow that accepts
`script`, `name`, `scriptPath`, `args`, and `resumeFromRunId`, then returns a
background task id and optional workflow run id.

Codex does not expose the same dynamic workflow DSL. Codex app-server can run
Yoke portable workflows over turns and has native subagent/collaboration events,
but Yoke should not pretend those are Claude-style dynamic workflows.

Eve reinforces the same shape: filesystem-first source artifacts are separate
from runtime/provider execution. Yoke keeps `Workflow(script=...)` as a source
artifact and requires provider-native workflow support before execution.

Sources:

- https://code.claude.com/docs/en/agent-sdk/typescript
- ../eve/README.md
- ../eve/docs/subagents.mdx
