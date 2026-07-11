# Workflows carry run options

Yoke workflows now carry a shared `RunOptions` object through `WorkflowOptions.run`.

This matters because workflows are not just a list of prompts. A real workflow often needs the same goal, permissions, effort, output schema, and provider-specific options on every provider turn. Before this slice, `WorkflowOptions` only had concurrency, fail-fast, and output schema. That made it impossible to run a whole workflow under one Codex collaboration mode or one explicit Yoke goal without adding ad hoc step machinery later.

The public shape is now:

```python
result = await harness.workflow(
    workflow,
    "write release notes",
    WorkflowOptions(
        run=RunOptions(
            goal=Goal("Finish the workflow safely."),
            permissions=Permissions(network=True),
            provider=ProviderOptions(...),
        ),
        concurrency=2,
    ),
)
```

Each step receives a copy of `WorkflowOptions.run`. The output schema precedence is:

1. `Step.output_schema`
2. `WorkflowOptions.run.output_schema`
3. legacy `WorkflowOptions.output_schema`

`Step.agent` now defaults to `"main"`, so simple folder-authored workflows do not need to repeat the root agent on every step.

Research note:

Claude dynamic workflows are not just DAG YAML. The TypeScript Agent SDK exposes a `Workflow` tool that runs a script in the background to coordinate many subagents and return one consolidated result. That is stronger than Yoke's current Python DAG runner. Yoke should keep its current runner as portable/emulated workflow support, and later add a provider-native Claude TypeScript workflow adapter or script compiler rather than pretending the current DAG is the same primitive.

Codex documents workflows as usage patterns and subagent workflows rather than a portable SDK-native workflow runtime. For Codex, Yoke's portable DAG runner plus Codex custom agents/collaboration tooling is the right near-term shape.
