# 0164 - Claude workflow bundles

## Context

Yoke now has two workflow bodies: portable step DAGs and provider-native scripts. The script body is aligned with Claude dynamic workflows, where saved workflows live under `.claude/workflows/` and contain JavaScript with a `meta` export plus top-level orchestration code.

A Yoke folder is the source format. A provider bundle is the explicit compiled artifact format. Script workflows should therefore compile to Claude workflow files the same way subagents compile to `.claude/agents/*.md` and skills compile to `.claude/skills/<name>/SKILL.md`.

## Yoke change

Claude bundles now emit script workflow artifacts:

```text
.claude/workflows/<workflow>.js
```

If the Yoke workflow script already contains `export const meta`, Yoke preserves it exactly. Otherwise Yoke prepends a generated `meta` export using the `Workflow.name` and `Workflow.description` fields.

Artifact metadata uses `kind="claude_workflow"` and includes lowering text so callers can explain why the file exists.

## Provider boundary

Codex bundles do not emit script workflow files. Codex documents workflows mostly as usage patterns, goals, subagents, skills, and external orchestration. It does not expose Claude's dynamic workflow JavaScript DSL. Keeping Claude workflow bundling Claude-only avoids pretending the providers share a native workflow format.

## Verification

- `PYTHONPATH=src uv run pytest tests/test_artifacts.py` -> 5 passed.
- `uv run ruff check src/yoke/artifacts.py tests/test_artifacts.py` -> passed.
