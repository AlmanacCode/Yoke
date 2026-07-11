# Native workflow is an adapter port

Date: 2026-07-04

Yoke now has an explicit provider-native workflow port on `ProviderAdapter`.

Portable step workflows still run in `yoke.workflows` as a small dependency DAG over harness turns. Script workflows and `WorkflowOptions(native=True)` delegate to the selected adapter instead.

This keeps the ownership line clean:

- Yoke owns portable orchestration.
- Provider adapters own provider-native workflow execution.
- CodeAlmanac and other apps own durable jobs, retries, cancellation policy, and audit history above Yoke.

The distinction matters because Claude and Codex do not expose the same workflow primitive. Claude TypeScript SDK documents a native Workflow tool shape. Codex app-server documents rich sessions, streamed events, approvals, native goals, and subagent activity, but current public docs do not show a matching provider workflow DSL. Yoke should not invent a fake common denominator here.

`WorkflowRun.mode` is the result-side truth. Portable DAG execution returns `yoke_portable`. Adapter-owned native execution returns `provider_native`.
