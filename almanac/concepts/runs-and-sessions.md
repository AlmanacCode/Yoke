---
title: "Runs And Sessions"
summary: "Runs are stored execution results, while sessions are live or provider-persisted conversation handles used to send turns."
topics: [concepts, runtime]
sources:
  - id: models
    type: file
    path: src/yoke/models.py
  - id: store
    type: file
    path: src/yoke/store.py
  - id: session-note
    type: file
    path: docs/notes/0099-provider-session-id-is-separate-from-session-id.md
---

# Runs And Sessions

Runs and sessions are related but separate runtime concepts in Yoke. A `Run` is the result of one execution: provider, surface, status, output, structured data, events, session, usage, and failure details [@models]. A `Session` is a handle for an ongoing or resumable provider conversation, with a Yoke live id, an optional provider-persisted id, agent context, working directory, permissions, and goal state [@models]. `RunStore` persists run or workflow snapshots under `.yoke/runs/` [@store].

## Runs

A run is the result object returned by one-shot harness calls and session turns. It has a provider-neutral status of `succeeded`, `failed`, or `cancelled`, plus optional output, parsed data, normalized events, usage, failure information, and an attached session [@models].

`Run.provider_session_id` is computed from the attached session when available, or from the latest event that carries a provider session id [@models]. This lets a run preserve the provider conversation identity even when the adapter learns it from the event stream.

## Sessions

A session is the object used for ongoing interaction. It can send a turn with `run`, stream a turn with `stream`, read or mutate provider goal state when supported, interrupt, compact, rename, tag, fork, and close through the provider adapter [@models].

Yoke distinguishes `Session.id` from `Session.provider_session_id`. The note explains that `Session.id` is the Yoke live-session key used by adapters to find local process state, while `provider_session_id` is the provider-persisted conversation id when the provider exposes one [@session-note]. This distinction matters because some providers reveal persisted ids only after a run starts [@session-note].

## Turns

A turn is the input sent inside a session. The `Turn` model carries a prompt and optional id or model override [@models]. `Session.run()` wraps the prompt in a `Turn` and asks the adapter to send it; `Session.stream()` does the same but yields [Normalized Events](normalized-events) as the provider reports progress [@models].

The distinction is simple: the session is the conversation handle, the turn is one input to that handle, and the run is the collected result from that input.

## Stored snapshots

`RunStore` writes an inspectable snapshot under `.yoke/runs/<run_id>/` [@store]. A stored run has `record.json`, `result.json`, and optionally `events.jsonl`; workflow results use the same store and collect events from their step runs [@store]. [CLI And Run Storage](../reference/cli-and-run-storage) defines the shell commands that create and inspect those snapshots.

A stored record keeps metadata such as kind, provider, surface, status, cwd, agent, collection, provider session id, paths, and event count [@store]. For one-shot runs and workflows, the stored record gets that provider session id only from the attached session on the run or workflow step, while `Run.provider_session_id` can still fall back to event-derived ids inside the result model [@store] [@models].

[Runtime Flow](../architecture/runtime-flow) explains where this snapshot step sits in the larger execution path.

## Workflow runs

Workflows have their own result model, `WorkflowRun`. It records the workflow name, run mode, optional run id, provider, surface, status, step results, traces, output, data, and failure [@models]. When stored, `RunStore` marks the record kind as `workflow` and derives the record's provider session id from the first workflow step with an attached session provider id [@store]. See [Workflows](workflows) for the orchestration model that produces those results.
