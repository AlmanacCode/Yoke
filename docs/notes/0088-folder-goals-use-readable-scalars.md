# 0088 - Folder goals use readable scalars

Yoke folders now write a simple `Goal("Finish safely.")` as:

```yaml
goal: Finish safely.
```

Goals with additional state still write as the SDK-shaped mapping:

```yaml
goal:
  objective: Finish safely.
  token_budget: 10000
```

This keeps the folder format pleasant to author by hand while preserving the
full Pydantic model when budgets, status, or usage fields matter.

Workflow loading also now validates the full workflow mapping through the
`Workflow` model instead of manually reconstructing selected fields. The folder
loader should behave like another SDK entrypoint, not a lossy importer.
