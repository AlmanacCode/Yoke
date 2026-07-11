# Agent save prefers workflow folders

`Agent.save()` now writes workflows as `workflows/<name>/` directories instead of single YAML files.

Each step becomes `<step>.md`; the body is the prompt, and frontmatter carries non-default step fields such as `agent`, `depends_on`, and `output_schema`. `workflow.yaml` is written only when workflow metadata such as `description` is present.

This keeps the SDK object model and folder model aligned. A workflow created in Python saves into the same readable path-derived format that `Agent.from_folder()` loads.

The loader still accepts legacy/compact `workflows/*.yaml` files. The folder format is the preferred authored shape because it is easier to review, edit, and keep close to Eve's path-derived design instinct.
