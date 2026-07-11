# Native workflow is a separate feature

2026-07-04

Yoke now distinguishes portable workflows from provider-native workflow primitives.

`Feature.WORKFLOW` means Yoke can execute a workflow shape. That can be native, compiled, or emulated. Today Python execution uses Yoke-owned orchestration over provider turns.

`Feature.NATIVE_WORKFLOW` means the selected surface exposes a provider-native workflow primitive. Current research points to Claude's TypeScript Agent SDK Workflow tool. Yoke marks that surface as conceptual and not runnable from the Python package yet. Codex CLI, Codex Python SDK, and Codex app-server stay unsupported for native workflows because their documented primitives are turns, threads, app-server notifications, collaboration tools, and goals rather than a provider workflow DSL.

`WorkflowOptions(native=True)` now requests both `workflow` and `native_workflow`. That keeps the default readable:

```python
await harness.workflow(workflow, "ship this")
```

and keeps native selection explicit:

```python
harness.plan(WorkflowOptions(native=True), runnable=False)
```

This preserves the user promise: Yoke is portable, but it does not hide where providers have different real shapes.
