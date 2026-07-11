# Eve folder boundary

Re-read local Eve at `/Users/rohan/Desktop/Projects/eve` on 2026-07-04.

Eve's README describes a filesystem-first durable agent layout:

```text
agent/
  agent.ts
  instructions.md
  tools/
  skills/
  channels/
  schedules/
```

The local source also has durable runtime pieces:

- `packages/eve/src/execution/workflow-runtime.ts`
- `packages/eve/src/execution/turn-workflow.ts`
- `packages/eve/src/harness/workflow-lifecycle.ts`
- `packages/eve/src/runtime/resolve-agent-graph.ts`
- `packages/eve/src/runtime/resolve-dynamic-skill.ts`
- `packages/eve/src/runtime/resolve-dynamic-tool.ts`

Yoke should stay inspired by this, but not copy it prematurely.

Current Yoke boundary:

- Yoke owns agent definitions, folder loading, provider adapters, sessions, goals, events, and simple workflows.
- Providers still own the agent loop.
- Yoke does not yet own durable workflow state, schedules, channels, sandbox lifecycle, or typed tool execution.

That means `tools/`, `channels/`, and `schedules/` should not be added as public folder directories until Yoke has a concrete runtime story for them.

The concrete gap fixed in this slice was smaller: `Step.output_schema` existed in the public model but workflow execution ignored it. Workflows now pass each step's `output_schema` into the underlying provider run. If a step has no schema, the workflow-level `WorkflowOptions.output_schema` is used as the default.

This keeps the folder model honest: do not expose directories or fields the runtime ignores.

Verification:

- A fake provider adapter recorded workflow run options for two steps.
- The first step received its own schema: `{"type": "object", "title": "StepSchema"}`.
- The second step received the workflow fallback schema: `{"type": "object", "title": "WorkflowFallback"}`.
- The same behavior is now covered by `tests/test_workflows.py`.
