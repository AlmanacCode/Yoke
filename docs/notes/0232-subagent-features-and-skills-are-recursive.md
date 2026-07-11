# Subagent features and skills are recursive

2026-07-04

Yoke now treats subagent shape as part of the root agent shape for planning and provider bundles.

`Agent.features()` already reported root-level `goal`, `skills`, declared `subagents`, and `workflows`. It now also walks declared subagents and adds their implied features, deduped in first-seen order. A root agent with a researcher subagent that has a goal, skill, or workflow therefore plans for those features before execution.

Provider bundle generation now collects inline skills recursively from the agent tree. This matters for Claude custom subagents because their frontmatter can reference subagent skills by name; the bundle must also emit the matching `.claude/skills/<name>/SKILL.md` file. Codex bundles now emit recursive inline skills under `.agents/skills/` as well.

This keeps three surfaces aligned:

- folder save already recurses into `subagents/`
- planning now recurses into subagent features
- provider bundles now recurse into subagent inline skill artifacts

Verification:

- `PYTHONPATH=src uv run pytest tests/test_capabilities.py tests/test_artifacts.py tests/test_folders.py`
- `PYTHONPATH=src uv run ruff check src/yoke/models.py src/yoke/artifacts.py tests/test_capabilities.py tests/test_artifacts.py`
