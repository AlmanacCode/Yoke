---
title: "Architecture"
summary: "The Architecture hub routes readers through Yoke's runtime flow and product-integration boundaries."
topics: [architecture, wiki]
sources: []
---

# Architecture

The architecture pages explain the runtime and integration boundaries that keep
Yoke provider-neutral. Read them when a change affects execution flow,
persistence, provider adapters, or an embedding product such as `codealmanac`.

## Runtime

Start with [Runtime Flow](runtime-flow) when changing how prompts become runs,
sessions, normalized events, streamed turns, or `.yoke` snapshots. It connects
the [Yoke Harness](../concepts/yoke-harness), [Runs And Sessions](../concepts/runs-and-sessions),
[Normalized Events](../concepts/normalized-events), and
[CLI And Run Storage](../reference/cli-and-run-storage) pages into one
execution path.

Read [Runtime Deployments](runtime-deployments) when a change touches
generated provider files, `runtime_root`, cleanup, or the split between live
provider projections and durable bundle exports.

Read [Capability Planning](capability-planning) when a change adds or changes
features that depend on the selected provider surface. It explains how agent
and option requirements become a surface plan before provider execution starts.

Read [Workflows](../concepts/workflows) when runtime changes touch multi-step
agent orchestration. That page explains which workflow shapes are portable Yoke
execution and which require provider-native surface support.

Read [Provider Surfaces](../concepts/provider-surfaces) when runtime behavior
depends on the exact Claude or Codex entrypoint. That concept page is the
architecture-facing map for capability planning.

## Integration

Read [codealmanac Integration](codealmanac-integration) before changing the
boundary between Yoke and `codealmanac`. It records where `codealmanac` owns
wiki lifecycle work and where Yoke owns agent definitions, provider surfaces,
runtime environment, and harness execution.
