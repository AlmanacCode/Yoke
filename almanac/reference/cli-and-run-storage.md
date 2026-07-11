---
title: "CLI And Run Storage"
summary: "The Yoke CLI loads collection agents, executes runs or workflows, and writes inspectable snapshots under a chosen .yoke store."
topics: [reference, cli, runtime, authoring]
sources:
  - id: cli
    type: file
    path: src/yoke/cli.py
  - id: store
    type: file
    path: src/yoke/store.py
  - id: reference
    type: file
    path: docs/reference.md
  - id: cli-tests
    type: file
    path: tests/test_cli.py
  - id: store-tests
    type: file
    path: tests/test_store.py
---

The Yoke CLI is the shell surface for folder-authored agents. It loads a named agent from a collection folder, binds it to a [Yoke Harness](../concepts/yoke-harness), runs a command, and stores the result in a local `.yoke` run store when the command produces an execution result [@cli]. This makes CLI runs inspectable without changing the provider-native transcript locations that Claude or Codex may maintain themselves [@reference].

## Commands that execute work

`yoke run <collection> <agent> <prompt>` loads `yoke.yaml` from the collection folder, resolves the named agent, creates a harness with the CLI `--provider` value or the collection `default_provider`, executes one prompt, records the result, prints the run id, and then prints output when present [@cli] [@cli-tests]. The command accepts `--cwd` for the harness working directory and `--store` for the root that contains `.yoke`-style run records [@cli].

`yoke workflow <collection> <agent> <workflow> [prompt]` uses the same collection loading path, but calls `Harness.workflow(...)` and records the returned workflow result [@cli]. Its flags map onto `WorkflowOptions`: `--native`, `--resume`, `--concurrency`, `--channel`, and `--fail-fast` or `--no-fail-fast` [@cli]. The workflow input is either the positional prompt or JSON from `--args`; passing both is rejected, and invalid JSON in `--args` exits before the provider run starts [@cli].

## Commands that inspect or prepare

`yoke explain <collection> <agent>` loads the same collection agent but does not call the provider. It prints the harness explanation JSON, including requested features supplied with repeated `--feature` flags [@cli].

`yoke status <collection> <agent>` calls the selected harness status check and prints readiness plus capability sections for goals, workflows, subagents, skills, control, permissions, history, and exposure [@cli]. Use it when a caller needs machine-readable readiness and semantic support details before running an agent.

`yoke install <collection> <agent>` writes provider-native bundle files for a folder-authored agent [@cli]. It requires either `--provider` or a collection `default_provider`, accepts an optional `--surface`, and delegates the write to the same bundle path exposed by `agent.bundle(...)` [@cli] [@reference].

## Stored run shape

`RunStore.at(path)` treats `path` as the store root and writes run directories under `path/runs/` [@store]. The default CLI store is `.yoke`, so default CLI executions write under `.yoke/runs/<run_id>/` [@cli] [@store].

Each stored result has `record.json` and `result.json`; `events.jsonl` exists only when the run or workflow has normalized events [@store]. `record.json` is the inspection index. It records the generated Yoke run id, kind, provider, surface, status, cwd, agent, collection, provider session id, paths to stored files, and event count [@store]. `result.json` stores the provider-neutral result without volatile raw provider objects, and `events.jsonl` stores normalized events as JSON Lines without raw provider objects [@store].

Workflow results use the same store. The record kind becomes `workflow`, workflow events are collected from step runs, and the stored provider session id is the first provider session id found in those step runs [@store] [@store-tests].

## Inspection commands

`yoke runs` lists stored run records in newest-first order from the selected store [@cli] [@store]. `yoke show <id>` prints the selected `record.json`, and `yoke events <id>` prints `events.jsonl` for that run when it exists [@cli].

These commands are local inspection tools. They read the Yoke snapshot under the configured store; they do not replay provider-native histories or search provider transcript directories [@reference].
