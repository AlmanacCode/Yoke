---
title: "Decisions"
summary: "The Decisions hub records the architectural choices that constrain Yoke's provider surfaces and product integrations."
topics: [decisions, wiki]
sources: []
---

# Decisions

The decision pages explain why Yoke has its current shape. Read them when a
change may reverse an existing boundary rather than only extend it.

## Provider Boundaries

Start with [Provider Surfaces Are First-Class](provider-surfaces-first-class)
before changing capability planning, defaults, or surface naming. It records
why Yoke checks features against exact Claude and Codex surfaces instead of
treating a provider name as enough information. For the current model, read
[Provider Surfaces](../concepts/provider-surfaces) and
[Runtime Flow](../architecture/runtime-flow).

Read [codealmanac Uses Yoke-Only Harness Adapters](codealmanac-uses-yoke-only-harness-adapters)
before changing the product integration boundary. It records why `codealmanac`
keeps lifecycle work in the product while routing Claude and Codex execution
through Yoke. For the current architecture, read
[codealmanac Integration](../architecture/codealmanac-integration).
