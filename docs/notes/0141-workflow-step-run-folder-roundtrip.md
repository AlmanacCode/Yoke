# Workflow step run options round-trip through folders

Date: 2026-07-04

Yoke folder workflows now preserve `Step.run`.

`Step.run` was added so workflow defaults can be overridden on one node: a verification step can use a read-only permission posture, a final step can use a different output schema, or one step can carry a tighter goal. The loader already accepted `run:` in markdown workflow step frontmatter. The folder writer now emits `run:` when a step has runtime overrides.

Example frontmatter:

```yaml
agent: reviewer
depends_on: draft
run:
  goal:
    objective: Verify safely without editing files.
  permissions:
    access: read
```

Eve check: `../eve/docs/reference/project-layout.md` uses path-derived identity and authored slots under `agent/`. Names come from paths unless a human has to override them. That supports Yoke's current folder direction: workflows are directories, step names come from markdown filenames, and only non-default runtime details appear in frontmatter.

Design implication: Yoke's folder API and Python SDK should stay peers. If an option can be expressed cleanly in Python, it should usually round-trip through the folder unless it is inherently non-serializable, like a live callback.

Next pressure test: decide whether provider-specific callback-like options need an explicit "SDK-only" marker in reports/docs so folder users are not surprised when a field cannot be saved.
