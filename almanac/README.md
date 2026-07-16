---
title: Yoke Wiki
topics: [wiki]
sources: []
---

# Yoke Wiki

This wiki is the durable project memory for Yoke. It explains the shared
vocabulary behind the provider-neutral harness, then routes readers into the
runtime, authoring, provider-surface, and product-integration boundaries.

## Where to start

For a compact map of the vocabulary, read [Concepts](concepts).

Start with [Yoke Harness](concepts/yoke-harness). It is the central abstraction
that binds an agent definition to a Claude or Codex surface.

For provider planning, read [Provider Surfaces](concepts/provider-surfaces).
That page explains why capability checks are surface-specific rather than only
provider-specific.

For filesystem-authored agents, read [Agent Folders](concepts/agent-folders).
Use it before changing folder agents, skills, subagents, workflows, or named
collections.

For multi-step agent work, read [Workflows](concepts/workflows). It separates
portable Yoke step DAGs from provider-native workflow artifacts.

For architecture boundaries, read [Architecture](architecture).

For provider feature checks, read
[Capability Planning](architecture/capability-planning). It explains how agent
and option requirements resolve to a concrete provider surface before execution.

For architectural choices that should not be reversed accidentally, read
[Decisions](decisions). The most important ones are
[Provider Surfaces Are First-Class](decisions/provider-surfaces-first-class)
and [codealmanac Uses Yoke-Only Harness Adapters](decisions/codealmanac-uses-yoke-only-harness-adapters).

For execution state, read [Runs And Sessions](concepts/runs-and-sessions),
[Normalized Events](concepts/normalized-events), and
[Runtime Flow](architecture/runtime-flow), then use
[CLI And Run Storage](reference/cli-and-run-storage) for exact shell behavior.
Together they explain the difference between live conversations, collected run
results, event streams, and `.yoke/runs/` snapshots.
When a local CLI run needs inspection, use
[Debug CLI Runs](guides/debug-cli-runs) as the task path.

For product embedding, read
[codealmanac Integration](architecture/codealmanac-integration). It records the
thin adapter boundary where `codealmanac` owns wiki lifecycle work and Yoke owns
agent definitions, surfaces, and harness execution.

For future context design, read [Knowledge Packages](concepts/knowledge-packages).
That page is deliberately marked as a proposed primitive, not a shipped folder
contract.

## Maintenance standard

Keep pages focused on durable knowledge a future agent would otherwise have to
rediscover: decisions, cross-file flows, invariants, incidents, gotchas,
operating procedures, and project context.

Use normal Markdown links between pages, and put file evidence in `sources:`.
Do not use the wiki as a scratchpad for inventories, temporary plans, or raw
activity logs.
