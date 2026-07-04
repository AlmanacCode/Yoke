# 0009: Workflows are Yoke orchestration first

Slice date: 2026-07-04

## Research pressure

Eve has real workflow machinery. Files such as `workflow-runtime.ts`,
`workflow-entry.ts`, `turn-workflow.ts`, and `workflow-lifecycle.ts` show that
Eve workflows are durable runtime execution: turns, action state, callbacks,
continuations, sandboxing, and subagent dispatch all sit inside the workflow
world.

Claude Agent SDK does not expose a portable "workflow" object in the Python SDK
surface read here. It exposes strong primitives instead:

- live sessions,
- programmatic subagents,
- filesystem agents/settings,
- hooks,
- MCP,
- custom commands/settings,
- session stores.

Codex TypeScript SDK also exposes primitives:

- threads,
- repeated turns,
- streamed events,
- structured output.

Codex app-server is closer to a control plane than a workflow DSL. It owns
thread lifecycle, listeners, notifications, approvals, and native mutable goals.

## Decision

The first Yoke workflow is Yoke-owned orchestration over existing harness calls.

It is not provider-native. It does not claim Claude, Codex CLI, or Codex
app-server expose the same workflow primitive.

Public shape:

```python
workflow = Workflow(
    name="tiny-review",
    steps=(
        Step(name="draft", agent="main", prompt="Draft: {input}"),
        Step(name="review", agent="reviewer", depends_on=("draft",), prompt="{draft}"),
    ),
)

result = await harness.workflow(workflow, "write a changelog")
```

## Semantics

This slice supports:

- sequential steps,
- explicit dependencies,
- `main` / `root` agent aliases,
- subagent lookup through `harness.agent.subagents`,
- simple prompt formatting with `{input}` and prior step outputs.

The result is `WorkflowRun`, containing `StepResult` entries and the final
output.

## What is intentionally missing

This is not durable yet. It has no retries, no persisted event log, no
concurrency, no human approvals, no app-server native thread listener, and no
provider-side workflow dispatch tool.

Those should be added only when the surface demands them. Eve is the reference
for durable workflow machinery; this slice is the small Python SDK layer that
can later grow toward it.

## Real smoke

Command:

```bash
uv run --with claude-agent-sdk --with pydantic --with pyyaml python examples/workflow_claude.py
```

Result:

```text
good
```

This exercised `Harness.workflow(...)` with a main-agent step followed by a
subagent step on the real Claude Python SDK surface.
