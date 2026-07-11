# 0163 - Script workflows

## Context

Claude dynamic workflows are not just prompt-step DAGs. The current Claude docs describe saved workflows as JavaScript files under `.claude/workflows/` with a `meta` block and a script body. The body uses top-level `await`, calls helpers such as `agent()` and `pipeline()`, and keeps intermediate results in script variables instead of pushing every subagent result into the parent conversation.

That is a different primitive from Yoke's existing portable workflow DAG.

Codex docs use the word workflow mostly for development patterns, subagent workflows, goals, skills, and external orchestration. Codex does not currently expose the same script workflow DSL as Claude dynamic workflows. Codex can still run Yoke portable workflows through turns, or use skills/subagents/goals as provider-native patterns.

## Yoke change

`Workflow` now has two body shapes:

```python
Workflow(name="review", steps=(Step(...),))
Workflow(name="audit-routes", script="return await agent('Audit routes')")
```

A workflow must have either steps or script, not both.

Script workflows use `WorkflowLanguage.JAVASCRIPT` and round-trip through folders as:

```text
agent/workflows/audit-routes/
  workflow.yaml
  script.js
```

`workflow.yaml` carries metadata such as description and language. `script.js` carries the provider-native workflow script.

## Execution boundary

Yoke still executes only portable step workflows locally. Script workflows imply `Feature.NATIVE_WORKFLOW` during planning. If execution reaches the local Yoke DAG runner, it raises `UnsupportedFeature` with a clear message.

This keeps the API honest:

- Step workflows are portable Yoke orchestration over provider turns.
- Script workflows are provider-native workflow artifacts, currently aligned with Claude dynamic workflows.
- Codex can still use goals, subagents, skills, app-server events, and Yoke DAGs without pretending it has Claude's script workflow DSL.

## Sources checked

- https://code.claude.com/docs/en/workflows
- https://developers.openai.com/codex/workflows
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/concepts/subagents
- https://developers.openai.com/codex/use-cases/reusable-codex-skills

## Verification

- `PYTHONPATH=src uv run pytest tests/test_workflows.py tests/test_folders.py` -> 25 passed.
- `uv run ruff check src/yoke/models.py src/yoke/workflows.py src/yoke/folders.py src/yoke/loader.py tests/test_workflows.py tests/test_folders.py` -> passed.
