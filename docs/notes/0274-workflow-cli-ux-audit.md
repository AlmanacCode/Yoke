# 0274 - Workflow CLI UX audit

Date: 2026-07-04

## Recommendation

Add a single verb that keeps the existing folder CLI grammar:

```bash
yoke workflow <collection> <agent> <workflow> "<prompt>"
```

Examples:

```bash
yoke workflow agents codealmanac review "Audit the release diff"
yoke workflow agents codealmanac review "Audit the release diff" --provider codex:app --cwd .
yoke workflow agents codealmanac review "Audit the release diff" --concurrency 2 --no-fail-fast
yoke workflow agents codealmanac script-audit --native --args '{"scope":"routes"}'
```

This should mirror the current command family:

- `yoke run agents codealmanac "Review this repo"` in `README.md`.
- `yoke explain agents codealmanac` in `README.md`.
- `yoke status agents codealmanac` in `README.md`.
- `yoke install agents codealmanac --provider codex:cli` in `README.md`.
- The current parser already treats `collection` and `agent` as the first two operands for `run`, `explain`, `status`, and `install` in `src/yoke/cli.py`.

Do not use `yoke run --workflow review ...`. Workflows are not just a run option; `Harness.workflow(...)` is a separate SDK verb in `src/yoke/models.py`, and workflow results store as `kind: "workflow"` in `src/yoke/store.py`.

## Prompt behavior

The fourth positional argument is the root workflow input. It should map directly to the `prompt` argument of `Harness.workflow(workflow, prompt, options)` in `src/yoke/models.py`.

Portable step workflows use `{input}` as this root prompt. Step outputs fill `{step_name}` placeholders, and unresolved placeholders should keep using the workflow runner's existing validation in `src/yoke/workflows.py`.

For Python program workflows and provider-native workflows, pass the same positional input through unless `--args` is provided. If both a prompt and `--args` are present, `--args` should be the explicit structured argument value and the prompt should be rejected. This avoids guessing how to merge text input with native workflow arguments.

## Options

Start with only options that already exist in the SDK model:

```bash
--provider <provider:surface>   # same meaning as run/explain/status/install
--cwd <path>                    # same harness cwd as run/status
--store <path>                  # same .yoke store root as run/runs/show/events
--concurrency <n>               # WorkflowOptions.concurrency
--fail-fast / --no-fail-fast    # WorkflowOptions.fail_fast
--native                        # WorkflowOptions.native
--channel <channel>             # WorkflowOptions.channel
--args <json>                   # Workflow.args-style structured input for program/native runs
```

Do not add step-level CLI flags yet. Step options already live in folder source as `run:` frontmatter, covered by `tests/test_folders.py`, and `src/yoke/workflows.py` merges workflow-level defaults with `Step.run`.

Do not add provider-specific option flags yet. The CLI should not become a second serialization format for `RunOptions.provider`. Folder YAML and Python SDK objects already own that.

## Storage

`yoke workflow` should record through the same store as `yoke run`:

```text
.yoke/
  runs/
    run_<id>/
      record.json
      result.json
      events.jsonl
```

`RunStore.record(...)` already accepts `WorkflowRun` and writes `record.kind == "workflow"` in `src/yoke/store.py`. The command should print the record id first, then final `WorkflowRun.output` when present, matching `yoke run`.

`yoke runs`, `yoke show`, and `yoke events` should continue to work without a new inspection command. `tests/test_store.py` already covers workflow event snapshots.

## Implementation shape

Keep the CLI as a thin adapter:

```text
parse args
-> Collection.from_folder(collection)
-> collection.agent(agent)
-> Harness(provider, agent=agent, cwd=cwd)
-> harness.workflow(workflow_name, prompt_or_args, WorkflowOptions(...))
-> RunStore.at(store).record(result, agent=agent_name, collection=collection, cwd=cwd)
```

This matches the CLI/store boundary in `docs/notes/0270-cli-collection-run-store.md` and the install boundary in `docs/notes/0273-cli-install-provider-bundles.md`.

## Pitfalls to avoid

- Do not add a root `yoke.yaml`, registry, or workflow lookup outside the collection. `docs/notes/0268-agent-collection-folder-contract.md` says `agents/yoke.yaml` is the only collection shape.
- Do not duplicate workflow scheduling in `src/yoke/cli.py`. `src/yoke/workflows.py` already owns dependencies, prompt rendering, fail-fast, concurrency, and status.
- Do not treat native script workflows as portable DAGs. `docs/notes/0163-script-workflows.md` and `docs/notes/0170-workflow-status-report.md` keep portable and provider-native workflow modes separate.
- Do not silently drop runtime-only values. `docs/notes/0142-runtime-only-options-are-visible.md` and `docs/notes/0143-folder-save-refuses-runtime-only-options.md` make SDK-only callbacks explicit.
- Do not invent new run result semantics. `docs/notes/0033-run-status-is-public-contract.md` and `docs/notes/0034-workflows-use-run-status.md` say failures are result data when the provider turn completed.
- Do not make `yoke workflow` install provider files as a side effect. `yoke install` is the explicit provider-artifact command.
