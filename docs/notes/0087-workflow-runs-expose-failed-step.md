# Workflow runs expose failed step

Yoke workflows are small in-process DAGs over provider turns. They are not a durable workflow runtime yet.

`WorkflowRun.failed_step` now returns the first failed `StepResult`, or `None` when every step succeeded. This keeps failure handling readable without making callers scan `WorkflowRun.steps` manually.

The property is deliberately diagnostic. It does not add another workflow state machine or approve/retry protocol. The run still carries `status`, `failure`, ordered `steps`, final `output`, and parsed `data`.

This matches the current workflow scope: enough structure for common orchestration and debugging, without pretending Yoke has Eve-style durable workflow semantics yet.
