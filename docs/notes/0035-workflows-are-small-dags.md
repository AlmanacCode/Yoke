# Workflows are small DAGs

Date: 2026-07-04

Yoke workflows are provider-neutral orchestration over harness runs.

They are not a Claude-only dynamic workflow feature, and they are not a Codex app-server primitive. The provider may still do its own planning inside each step.

The Yoke-owned workflow runner now treats a workflow as a small dependency graph:

- Explicit dependencies come from `Step.depends_on`.
- Prompt placeholders also imply dependencies, so `prompt="summarize {research}"` waits for the `research` step.
- `{input}` is the root user prompt, not a step dependency.
- Ready steps run concurrently up to `WorkflowOptions.concurrency`.
- Step results are returned in workflow declaration order, not completion order.
- `WorkflowOptions.fail_fast` controls whether scheduling stops after a failed step.

This makes `concurrency` a real option while keeping the API small:

```python
workflow = Workflow(
    name="write",
    steps=(
        Step(name="research", agent="researcher", prompt="Research {input}"),
        Step(name="review", agent="reviewer", prompt="Review {input}"),
        Step(name="draft", agent="writer", prompt="Use {research} and {review}"),
    ),
)

result = await harness.workflow(
    workflow,
    "Explain the harness boundary.",
    WorkflowOptions(concurrency=2),
)
```

This is deliberately not a durable job system. Apps that need persistence, retries, queues, audit logs, or product lifecycle state should own those above Yoke, the way CodeAlmanac owns jobs and mutation policy.
