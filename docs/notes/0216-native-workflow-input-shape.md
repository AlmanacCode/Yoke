# 0216 native workflow input shape

Date: 2026-07-04

The user pushed on whether Yoke workflows were implemented according to provider internals or as a simplified abstraction. The honest answer before this slice was mixed:

- `Workflow(steps=...)` is a simplified portable Yoke DAG over provider turns.
- `Workflow(script=...)` already implied `Feature.NATIVE_WORKFLOW`, but it modeled only one part of Claude's native Workflow tool input.

Claude's documented TypeScript Agent SDK `Workflow` tool accepts:

- `script`
- `name`
- `scriptPath`
- `args`
- `resumeFromRunId`

Yoke now models that native input shape through `Workflow.native_input()` and constructors:

- `Workflow.from_script(...)`
- `Workflow.from_file(...)`
- `Workflow.from_name(...)`

`Workflow` also has native fields:

- `script_path`
- `native_name`
- `args`
- `resume_from_run_id`

Design rule:

- Portable workflows remain `Workflow(steps=...)` and execute in `yoke.workflows`.
- Native workflows are any workflow with `script`, `script_path`, `native_name`, or `resume_from_run_id`, and they require `Feature.NATIVE_WORKFLOW`.
- A native workflow must include at least one of `script`, `native_name`, or `script_path`; `resume_from_run_id` alone is not a workflow target.
- Yoke still does not claim Claude Python SDK can execute the TypeScript-native Workflow tool. Native execution remains an adapter capability.

Codex still does not expose the same Workflow tool DSL in current docs. Codex's comparable primitives are goals, explicit subagent workflows, skills, and app-server collaboration events.

Verification:

```text
PYTHONPATH=src uv run pytest tests/test_workflows.py tests/test_folders.py tests/test_artifacts.py tests/test_capabilities.py
116 passed
uv run ruff check src/yoke/models.py src/yoke/workflows.py src/yoke/loader.py src/yoke/folders.py src/yoke/artifacts.py tests/test_workflows.py tests/test_folders.py
All checks passed
```

Sources:

- https://code.claude.com/docs/en/workflows
- https://code.claude.com/docs/en/agent-sdk/typescript
- https://developers.openai.com/codex/workflows
- https://developers.openai.com/codex/use-cases/follow-goals
