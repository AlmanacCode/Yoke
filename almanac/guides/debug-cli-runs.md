---
title: "Debug CLI Runs"
summary: "Use this guide when a Yoke CLI run, workflow, or stored event stream needs local inspection."
topics: [guides, cli, runtime]
sources:
  - id: cli
    type: file
    path: src/yoke/cli.py
  - id: store
    type: file
    path: src/yoke/store.py
  - id: cli-tests
    type: file
    path: tests/test_cli.py
  - id: store-tests
    type: file
    path: tests/test_store.py
---

# Debug CLI Runs

Use this guide when a `yoke run` or `yoke workflow` invocation finished, failed
to produce the expected output, or left a stored run that needs inspection. The
CLI writes completed execution results into a local store after the harness
returns, so debugging starts by finding the right store root and then reading
the stored record, result, and events [@cli] [@store].

For the exact command and file contract, keep [CLI And Run Storage](../reference/cli-and-run-storage)
open beside this guide.

## Find The Store Root

Start with the `--store` value used by the command. If no value was passed, the
CLI default is `.yoke` [@cli]. Pass that root to inspection commands; do not
append `runs/`, because `RunStore.at(path)` appends its own `runs` directory
before writing or reading records [@store].

If a run seems missing, check both the intended root and the common mistaken
shape:

```bash
yoke runs --store .yoke
find .yoke -maxdepth 3 -type f | sort
```

A record under `.yoke/runs/runs/<run_id>/` usually means a caller passed
`.yoke/runs` as the store root instead of `.yoke` [@store].

## Inspect The Record First

Use `yoke runs` to list records and `yoke show <id>` to print one
`record.json` [@cli]. The record is the local inspection index: it carries the
Yoke run id, kind, provider, surface, status, cwd, agent, collection, provider
session id, stored paths, and event count [@store].

Check these fields before opening provider transcripts. A wrong `cwd`,
collection, agent, provider, or surface usually points to command construction
or collection loading. A missing provider session id can be normal when the
provider did not report one, because Yoke stores it only when the result or
events expose it [@store].

## Read Events When Behavior Is Unclear

Use `yoke events <id>` when the record has events [@cli]. Events are JSON Lines
records, so shell tools can filter them without loading the whole result:

```bash
yoke events <run_id> --store .yoke | rg '"kind":'
```

No `events.jsonl` file does not always mean no run happened. The store writes
that file only when the completed run or workflow result contains normalized
events [@store].

## Separate Execution From Storage

The store records a completed `Run` or `WorkflowRun`; it is not the lifecycle
manager that keeps an in-progress execution alive [@store]. The CLI therefore
awaits `harness.run(...)` or `harness.workflow(...)` first, then records the
returned result [@cli].

If a process dies before the record write, the local `.yoke` snapshot can be
missing even when the provider kept its own native transcript. If an embedding
product needs stronger durability, it should persist live normalized events
through its own lifecycle store instead of treating `.yoke/runs/` as crash-safe
history. [Runtime Flow](../architecture/runtime-flow) explains that execution
and storage boundary.

## Verify The CLI Path

When changing CLI behavior, run the focused CLI and store tests before trusting
manual inspection output:

```bash
pytest tests/test_cli.py tests/test_store.py
```

The CLI tests cover run, workflow, explain, status, install, list, show, and
event-command behavior around the same parser and command functions used by the
shell entrypoint [@cli-tests]. The store tests cover writing result files,
event files, record indexes, workflow records, and newest-first run listings
[@store-tests].
