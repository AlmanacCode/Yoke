---
title: "Runtime Deployments"
summary: "Runtime deployments are temporary provider-native files derived from a Yoke agent for one live Claude or Codex execution boundary."
topics: [architecture, runtime, provider-surfaces, authoring]
sources:
  - id: readme
    type: file
    path: README.md
  - id: reference
    type: file
    path: docs/reference.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: runtime-deployment
    type: file
    path: src/yoke/providers/runtime_deployment.py
  - id: runtime-tests
    type: file
    path: tests/test_runtime_deployments.py
  - id: codex-app-server
    type: file
    path: src/yoke/providers/codex_app_server.py
  - id: claude-adapter
    type: file
    path: src/yoke/providers/claude.py
---

# Runtime Deployments

Runtime deployments are the temporary provider-native files Yoke derives from a
canonical agent when Claude SDK or Codex app-server needs files for a live run.
They are separate from authored [Agent Folders](../concepts/agent-folders) and
from durable bundle exports: `runtime_root` is a cache boundary outside
`Harness.cwd`, while `agent.bundle(...).write(...)` is the explicit way to
write project-owned provider files [@readme] [@reference] [@models].

## What Gets Written

`deploy_runtime(...)` creates a unique directory named
`yoke-<provider>-<pid>-...` under the selected runtime parent, then writes the
provider projection for one deployment [@runtime-deployment]. Codex deployments
can write custom-agent TOML, generated skill roots, role-specific skill roots,
skill enablement settings, and role-name maps for declared subagents
[@runtime-deployment]. Claude deployments write a local plugin only when inline
skills need to be exposed to the SDK [@runtime-deployment].

The projection is derived state. A `Harness` and `Session` can carry
`runtime_root`, but tests assert that it is excluded from serialized model
output and from `repr(...)` [@models] [@runtime-tests]. The runtime root must
also stay outside the harness working directory, so generated provider files do
not become part of the caller's authored project tree [@models]
[@runtime-tests].

## Lifetime And Cleanup

Each deployment has one owner-controlled lifetime. Claude one-shot and goal
runs clean up their deployment in a `finally` block after SDK query collection
finishes [@claude-adapter]. Codex app-server keeps deployments with the process
that owns the thread; closing the session releases that process, removes the
deployment on the last release, and terminates the process [@codex-app-server]
[@runtime-tests].

Startup failures also unwind the generated files. Tests cover Codex start
failure, goal setup failure, and shared-process release so the adapter does not
leave active deployment directories behind when session creation fails or when
the last session closes [@runtime-tests].

Yoke also reclaims stale owned directories before creating a new deployment.
The cleanup only removes `yoke-claude-<pid>-...` or `yoke-codex-<pid>-...`
directories whose owner process is gone; it leaves live-owner directories,
legacy names, symlinks, and unrelated cache folders alone
[@runtime-deployment] [@runtime-tests].

## Why It Matters

Runtime deployments let Yoke use provider-native affordances without changing
the source of truth for an agent. A folder-authored skill or subagent stays in
the Yoke agent model, and the selected provider surface receives only the files
needed for the live run [@runtime-deployment]. This keeps
[Runtime Flow](runtime-flow) provider-neutral while still allowing Codex and
Claude surfaces to receive the native artifacts they require.

The boundary is also a debugging clue. If provider-native skill or subagent
behavior is wrong, inspect the runtime deployment path and surface status before
changing authored agent folders. If durable provider files are required, use
the bundle export path instead of relying on `runtime_root` cache contents
[@reference].
