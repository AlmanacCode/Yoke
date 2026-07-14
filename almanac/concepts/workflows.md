---
title: "Workflows"
summary: "Workflows are Yoke-owned orchestration for multi-step harness work, with a separate boundary for provider-native workflow artifacts."
topics: [concepts, runtime, authoring, workflows]
sources:
  - id: workflow-note
    type: file
    path: docs/notes/0009-workflows.md
  - id: dag-note
    type: file
    path: docs/notes/0035-workflows-are-small-dags.md
  - id: script-note
    type: file
    path: docs/notes/0163-script-workflows.md
  - id: native-input-note
    type: file
    path: docs/notes/0216-native-workflow-input-shape.md
  - id: native-boundary-note
    type: file
    path: docs/notes/0242-native-workflow-boundary.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: runner
    type: file
    path: src/yoke/workflows.py
---

# Workflows

Workflows are Yoke's way to describe multi-step agent work without pretending
every provider exposes the same workflow runtime. Portable workflows are small
Yoke-owned DAGs over harness turns; native workflows are provider-native
artifacts that require a surface with a real native workflow hook
[@workflow-note] [@native-boundary-note]. This split matters because a
[Yoke Harness](yoke-harness) can run portable workflow steps across providers,
while provider-native scripts or named workflows must stay behind
[Provider Surfaces](provider-surfaces).

## Portable Step Workflows

A portable workflow is a `Workflow` with `Step` entries. Each step names an
agent, a prompt, optional dependencies, optional output schema, and optional run
options [@models]. The runner validates the step graph, renders prompts from
`{input}` and earlier step outputs, schedules ready steps with bounded
concurrency, and returns a `WorkflowRun` with ordered `StepResult` records
[@runner].

Dependencies can be explicit through `Step.depends_on` or implied by prompt
placeholders such as `{research}`. `{input}` means the root workflow input and
is not treated as a step dependency [@dag-note]. `WorkflowOptions.concurrency`
limits parallel ready steps, and `WorkflowOptions.fail_fast` controls whether
scheduling stops after a failed step [@dag-note].

Portable workflows are not durable jobs. The source note says apps that need
persistence, retries, queues, audit logs, or product lifecycle state should own
those above Yoke, the way `codealmanac` owns jobs and mutation policy
[@dag-note]. [Runs And Sessions](runs-and-sessions) and
[CLI And Run Storage](../reference/cli-and-run-storage) explain how completed
workflow results can be stored after execution.

## Native And Script Workflows

Yoke also models provider-native workflow artifacts separately. A `Workflow`
may carry a script, script path, native name, args, or resume id; those fields
form the native input shape and require the `native_workflow` feature
[@native-input-note] [@models].

Script workflows round-trip through agent folders as a workflow directory with
metadata and a script body, but Yoke does not execute them through the portable
DAG runner [@script-note]. If a native workflow request reaches a surface
without native workflow support, the shared runtime error names the provider,
surface, workflow, native input shape, and fallback to portable step workflows
[@native-boundary-note] [@runner].

## How This Fits Agent Packages

Workflows live beside instructions, skills, and subagents in
[Agent Folders](agent-folders). Folder-authored workflows can describe
portable step orchestration, file-backed scripts, or provider-native workflow
references, while the harness still decides at runtime whether the selected
surface can execute the requested shape [@script-note] [@native-input-note].

This keeps the authoring model honest. Agent packages can carry orchestration,
but Yoke must still report whether the surface will run it natively, run it as
portable steps, or reject it as unsupported.
