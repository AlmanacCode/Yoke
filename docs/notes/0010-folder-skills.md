# 0010: Folder skills and instructions

Slice date: 2026-07-04

## Research pressure

Eve treats skills as load-on-demand procedures. The important filesystem rules:

- flat markdown skills live under `agent/skills/<name>.md`;
- packaged skills live under `agent/skills/<name>/SKILL.md`;
- packaged `SKILL.md` carries `description` frontmatter;
- description is a routing hint, not a display label;
- skills are scoped to the agent that declares them;
- skills add instructions, not tools.

Eve also separates always-on instructions from skills:

- `instructions.md` is always-on identity and standing behavior;
- `instructions/` directory entries compose in sorted order;
- long situational procedures belong in skills.

Claude Python SDK supports native skills only when Claude can discover them.
Its `skills` option is a context filter, not a sandbox. Arbitrary Yoke folder
skills are not automatically a Claude-native skill installation.

Codex CLI has no arbitrary Yoke skill loader. It can only receive compiled text
through prompt/context unless a richer surface implements more.

## Decision

Yoke now parses folder skills into first-class `Skill` values:

- `name`
- `description`
- `path`
- `instructions`

The loader supports:

- `instructions.md`;
- sorted markdown files in `instructions/`;
- flat markdown skills;
- packaged `SKILL.md` skills with YAML frontmatter;
- workflows in `.yaml` and `.yml`.

`Agent.from_folder(path)` is now a public convenience over `load(path)`.

## Provider behavior

For Claude Python SDK and Codex CLI, Yoke currently compiles local skill
instructions into the prompt as optional procedure context.

This is compiled support, not native provider skill loading. A later Claude
surface adapter may materialize Yoke skills into a Claude-discoverable skill
directory or plugin. A later Codex app-server adapter may expose skills through
that surface if the protocol supports it.

## Real smoke target

`examples/folder_claude.py` loads `examples/folder_agent`, including its
`source-grounding` packaged skill and `tiny` workflow, then runs the workflow on
the real Claude Python SDK surface.

## First smoke result

`examples/load_folder.py` succeeded and showed that Yoke loaded:

- root instructions;
- the `source-grounding` packaged skill with frontmatter description;
- the `reviewer` subagent;
- the `tiny` workflow.

The first Claude smoke failed because the folder used `model: inherit`. That is
a subagent-style model hint, but the root Claude SDK `model` option expects a
real model id or `None`. Yoke now normalizes `inherit` to `None` when loading
folder config.

The second Claude smoke succeeded but included extra review-goal text after
`grounded`, because the example folder is a review agent with a review goal. The
smoke example now clears the goal after loading so it tests folder skills and
workflow execution without fighting the folder's review objective.

Final Claude smoke:

```bash
uv run --with claude-agent-sdk --with pydantic --with pyyaml python examples/folder_claude.py
```

Result:

```text
grounded
```
