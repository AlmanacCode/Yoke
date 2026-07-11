# Workflows use run status

Date: 2026-07-04

Yoke workflows should not treat every step output as successful context.

After `Run.status` became public contract, workflow orchestration needed to consume that contract:

- A successful step writes `run.output` into the workflow context.
- A failed step still records its `StepResult`.
- With `WorkflowOptions.fail_fast=True`, the workflow stops at the first failed step.
- With `WorkflowOptions.fail_fast=False`, the workflow continues and the final `WorkflowRun.status` remains `failed` if any step failed.

`WorkflowRun` now carries:

```python
class WorkflowRun(YokeModel):
    workflow: str
    status: RunStatus = RunStatus.SUCCEEDED
    steps: tuple[StepResult, ...] = ()
    output: str | None = None
    failure: Failure | None = None
```

This keeps workflows embedding-friendly. A caller can inspect the workflow result without catching exceptions or scraping step text, while still seeing every completed step.

Exceptions remain appropriate for invalid workflow structure, such as unknown step dependencies or a step referencing an unknown agent.
