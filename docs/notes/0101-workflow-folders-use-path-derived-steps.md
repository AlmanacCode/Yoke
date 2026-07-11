# Workflow folders use path-derived steps

Yoke now loads `workflows/<name>/*.md` as a workflow. The workflow name comes from the directory, and each step name comes from the markdown filename unless frontmatter overrides `name`.

Each markdown file body is the step prompt. Optional frontmatter supports `agent`, `depends_on` or `depends`, and `output_schema` or `schema`. `workflow.yaml` inside the directory can supply workflow metadata such as `description`.

This follows the Eve design instinct that authored identity should come from paths where possible. YAML still works for compact machine-authored workflows, but folder workflows are easier to read and edit by hand.

Example:

```text
agent/workflows/review/
  workflow.yaml
  draft.md
  review.md
```

This keeps the Yoke folder as source while preserving provider-neutral workflow execution.
