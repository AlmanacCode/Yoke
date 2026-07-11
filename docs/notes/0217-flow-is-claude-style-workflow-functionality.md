# 0217 Workflow is Claude-style workflow functionality

Date: 2026-07-04

The user clarified that "Claude-style workflow" means the functionality, not a literal copy of Claude's field names. The important behavior is:

- a workflow runs outside the parent conversational turn
- it can call subagents
- it can run work in parallel
- it can pipeline over a list of items
- it can group work into named phases
- it accepts args/context
- it returns one consolidated result
- it leaves traces/transcripts for the caller

Yoke now uses `Workflow` for that behavior after checking local Eve source:
Eve exposes a framework `Workflow` orchestration tool, not a separate workflow
mental model.

```python
workflow = Workflow("audit").run(program)
result = await harness.workflow(workflow, {"scope": "routes"})
```

Inside `program(ctx)`, the runtime exposes:

- `await ctx.agent(name, prompt)`
- `await ctx.parallel(...)`
- `await ctx.pipeline(items, worker, phase=...)`
- `async with ctx.phase(name)`
- `ctx.summarize(values)`
- `ctx.args`

`Workflow` now has three body shapes:

- `Workflow(...).run(handler)` is Yoke-owned Claude-style workflow functionality over provider turns.
- `Workflow(script/script_path/native_name/...)` models provider-native workflow tool input.
- `Workflow(steps=...)` is the older portable step DAG and remains supported for now.

Current limitations:

- `Workflow` program execution is immediate in-process orchestration, not durable background execution.
- Folder serialization is intentionally not added yet because a Python handler is a live SDK object.
- Provider-native lowering to Claude TypeScript Workflow tool remains future work.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_workflows.py tests/test_folders.py tests/test_artifacts.py tests/test_capabilities.py tests/test_public_api.py
121 passed
uv run ruff check src/yoke/programs.py src/yoke/models.py src/yoke/options.py src/yoke/__init__.py tests/test_flows.py
All checks passed
```

## Run identity slice

Workflow program runs now record a Yoke run spine:

- `WorkflowRun.run_id`
- `WorkflowRun.resume_from_run_id`
- `WorkflowTrace.id`
- `WorkflowOptions.resume`

If `WorkflowOptions.resume` is set, Yoke uses that value as the run id for the returned run and all traces. This is trace continuity, not durable cached replay yet. It prepares the API for a later runtime that can persist workflow state and resume or skip already-completed agent calls.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_results.py tests/test_public_api.py
11 passed
uv run ruff check src/yoke/programs.py src/yoke/models.py src/yoke/options.py tests/test_flows.py
All checks passed
```

## In-memory replay slice

Workflow now has a small replay seam:

- `WorkflowMemory`
- `WorkflowOptions(memory=...)`
- `WorkflowTrace.cached`

When a workflow is run with the same `WorkflowOptions.resume` value and the same `WorkflowMemory`, `ctx.agent(...)` reuses a previously successful run if the agent name, phase, prompt, and run options match. Changed prompts or options still run live.

This mirrors one Claude Workflow behavior at a Yoke level: unchanged agent calls can be reused when resuming a workflow. The current implementation is intentionally in-memory. A durable store can later implement the same `get(run_id, key)` / `put(run_id, key, run)` behavior without changing `ctx.agent(...)`.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_public_api.py
6 passed
uv run ruff check src/yoke/programs.py src/yoke/models.py src/yoke/options.py src/yoke/__init__.py tests/test_flows.py
All checks passed
```

## Durable replay slice

Workflow now has an explicit replay contract and a filesystem replay store:

- `WorkflowReplay`
- `WorkflowStore(path)`
- JSONL records keyed by workflow run id and deterministic agent-call key
- replay across fresh store instances, which models a new Python process

The public behavior stays the same as `WorkflowMemory`: `ctx.agent(...)` skips a
previously successful call when the same resume id, agent name, phase, prompt,
and run options are used. This makes the first durable version of Yoke's
Claude-style workflow replay behavior available through the `Workflow` API.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_public_api.py
7 passed
uv run ruff check src/yoke/programs.py src/yoke/replay.py src/yoke/options.py src/yoke/__init__.py tests/test_flows.py
All checks passed
```

## Breaking Workflow-only cleanup

The previous separate workflow-program concept was removed. Yoke now uses one public word, `Workflow`, for Python programs, portable step DAGs, and provider-native workflow scripts. The old runtime module was renamed from `flow.py` to
`programs.py` so internal code does not preserve the discarded vocabulary.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_public_api.py tests/test_smoke_harnesses.py
30 passed
uv run ruff check src/yoke/programs.py src/yoke/replay.py src/yoke/options.py src/yoke/models.py src/yoke/workflows.py src/yoke/__init__.py tests/test_flows.py tests/test_smoke_harnesses.py scripts/smoke_harnesses.py
All checks passed
```

## Folder-first Python workflow programs

Yoke folders now support Python workflow programs:

```text
agent/workflows/audit-routes/
  workflow.yaml
  workflow.py
```

`workflow.py` must define `main(ctx)`. `Agent.from_folder(...)` loads the file
as a `Workflow` with `program_path`, and `harness.workflow(...)` imports the
program at runtime. SDK users can create the same shape with
`Workflow.from_program("audit-routes", "agent/workflows/audit-routes/workflow.py")`.

This follows the Eve lesson that path-derived authored slots should be first
class. Yoke still differs intentionally: Eve does not ask users to write
Workflow SDK code directly, while Yoke exposes a small Python workflow program
because it is the SDK authoring layer over Claude/Codex harness turns.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_flows.py tests/test_folders.py tests/test_public_api.py
26 passed
uv run ruff check src/yoke/programs.py src/yoke/loader.py src/yoke/folders.py src/yoke/models.py src/yoke/workflows.py tests/test_flows.py tests/test_folders.py
All checks passed
```
