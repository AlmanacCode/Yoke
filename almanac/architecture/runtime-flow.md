---
title: "Runtime Flow"
summary: "Runtime flow explains how a Yoke harness turns prompts into runs, sessions, normalized events, and optional .yoke snapshots."
topics: [architecture, runtime, provider-surfaces]
sources:
  - id: readme
    type: file
    path: README.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: ports
    type: file
    path: src/yoke/ports.py
  - id: options
    type: file
    path: src/yoke/options.py
  - id: cli
    type: file
    path: src/yoke/cli.py
  - id: store
    type: file
    path: src/yoke/store.py
  - id: runtime-deployment
    type: file
    path: src/yoke/providers/runtime_deployment.py
  - id: runtime-deployment-tests
    type: file
    path: tests/test_runtime_deployments.py
  - id: codex-app-server
    type: file
    path: src/yoke/providers/codex_app_server.py
  - id: provider-audit
    type: file
    path: docs/provider-truth-audit-2026-07-11/worklog.md
  - id: codex-startup-transcript
    type: conversation
    path: /Users/rohan/.codex/sessions/2026/07/10/rollout-2026-07-10T19-50-43-019f4f15-9750-7373-bf99-6eb61ab7ab46.jsonl
---

# Runtime Flow

Yoke runtime flow starts when a [Yoke Harness](../concepts/yoke-harness)
receives a prompt or session turn, plans the required surface features, delegates
execution to a provider adapter, and receives a provider-neutral `Run` or
stream of [Normalized Events](../concepts/normalized-events) [@models]
[@ports]. Persistence is separate from execution: the CLI records completed runs
and workflows in a local store, but SDK callers only create `.yoke/runs/`
snapshots when they explicitly call the store API [@cli] [@store].

## Execution Boundary

The harness owns the provider-neutral entrypoint. `Harness.run(...)` validates
`RunOptions`, checks whether the selected surface supports the requested
features, then calls the adapter's `run(...)` method [@models] [@ports]. The
adapter owns the provider protocol from that point: Claude SDK messages, Codex
app-server notifications, Codex SDK events, and Codex CLI JSONL output all enter
Yoke through adapter code rather than through product services [@ports].
The surface selection and rejection rules for those feature checks are detailed
in [Capability Planning](capability-planning).

Streaming follows the same boundary. `Harness.stream(...)` creates or resumes a
session, asks the adapter to stream one turn, and yields normalized events
instead of waiting for a collected run result [@models] [@ports]. This gives
callers two shapes for the same provider activity: a collected run for normal
execution, or an event iterator when the product needs live updates.

## Runtime Deployments

Some provider-native features require files even when the canonical Yoke agent
is an in-memory model. Claude SDK and Codex app-server runs therefore create a
runtime deployment: an isolated provider projection under a temporary
`runtime_root` outside `Harness.cwd` [@runtime-deployment] [@runtime-deployment-tests].
The deployment writes provider files such as Codex custom-agent TOML, generated
skill roots, role-specific skill roots, and Claude local plugin files, then the
adapter passes those paths to the provider process for the live run
[@runtime-deployment].

The deployment is runtime state, not authored configuration. `runtime_root` is
excluded from harness and session serialization, must be outside `cwd`, and is
cleaned up when the owning session closes or when startup fails
[@runtime-deployment-tests]. A later deployment reclaims only stale
`yoke-<provider>-<pid>-...` directories whose owner process is gone, so cleanup
does not delete authored provider files or unrelated cache directories
[@runtime-deployment] [@runtime-deployment-tests].

The provider truth audit records the reason for this boundary: runtime files
can be immutable and session-scoped, but resumability needs durable metadata
that is safe to keep after the temporary files are removed [@provider-audit].
That keeps the provider projection reproducible without treating generated
files as source material.

## Codex App-Server Startup State

The Codex app-server adapter starts `codex app-server --listen stdio://`, sends
`initialize`, then starts, resumes, lists, reads, renames, or uses a thread
through JSON-RPC [@codex-app-server]. Each process receives the harness
environment, so an embedding caller can point several Yoke sessions at the same
`CODEX_HOME` and therefore the same Codex auth, config, and state files
[@codex-app-server].

A July 2026 investigation found that this startup path can race before the first
thread RPC when multiple stdio app-server processes initialize against the same
Codex home [@codex-startup-transcript]. The important boundary is not the
runtime deployment directory: the shared state is Codex's own home and auth
database, while Yoke's generated provider projection remains session-scoped
[@runtime-deployment] [@codex-startup-transcript]. Future fixes should
serialize process startup through `initialize` or add a narrow transient retry
around that phase; they should not duplicate `CODEX_HOME` trees, because that
would fork the external authentication and configuration state that Yoke is
supposed to reuse [@codex-startup-transcript].

## Sessions And Runs

Sessions and runs carry different identities. A [Runs And Sessions](../concepts/runs-and-sessions)
page defines a `Session` as the live or provider-persisted conversation handle,
while a `Run` is the collected result from one execution or session turn
[@models]. A session can send, stream, interrupt, compact, fork, rename, tag,
and close through adapter methods when the chosen surface supports those
operations [@models] [@ports].

The provider-persisted conversation id is optional and may be learned during a
run. `Run.provider_session_id` therefore resolves from the attached session when
one exists, or from the newest event that carries a provider session id
[@models]. This is why run storage records both Yoke run metadata and provider
session metadata instead of treating them as the same identifier.

## Event Delivery

Events are the bridge between provider activity and product state. A run can
carry collected events, `stream(...)` can yield them one at a time, and
`RunOptions(on_event=...)` can deliver each event to a synchronous callback
during supported one-shot runs [@models] [@options]. Because `on_event` is a
Python callable, `RunOptions` treats it as runtime-only data and declares the
`run_event_callbacks` feature only when the callback is present [@options].

The feature check matters. A product that asks for live event callbacks is not
only selecting a provider; it is asking for a surface that can deliver callback
events before the run is persisted [@options]. The callback path is therefore
part of surface planning, while stored `events.jsonl` files are a later snapshot
written from collected run or workflow events [@store].

## Storage Boundary

`RunStore` records completed `Run` and `WorkflowRun` objects under
`<store>/runs/<run_id>/` [@store]. It writes `result.json` without raw provider
objects, writes `events.jsonl` only when normalized events exist, and writes
`record.json` as the inspection index for provider, surface, status, cwd, agent,
collection, provider session id, stored paths, and event count [@store].

The CLI is the built-in store caller. `yoke run` and `yoke workflow` await the
harness result first, then call `RunStore.at(args.store).record(...)` [@cli].
This keeps execution and storage loosely coupled, but it also means the local
`.yoke` store is not a crash-safe lifecycle manager. Embedding products that
need stronger durability should persist live events through their own lifecycle
store instead of relying only on the post-run snapshot.

SDK callers should pass the store root to `RunStore.at(...)`, such as
`.yoke`, because the store appends `runs/` itself [@store]. The reference page
records this as a current gotcha: an older README snippet still shows
`.yoke/runs`, which would nest records under `.yoke/runs/runs/` with the
current implementation [@readme] [@store].

See [CLI And Run Storage](../reference/cli-and-run-storage) for exact commands,
file names, and inspection behavior.
