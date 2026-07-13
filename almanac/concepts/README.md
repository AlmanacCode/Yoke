---
title: "Concepts"
summary: "The Concepts hub routes readers through Yoke's core vocabulary: harnesses, provider surfaces, authoring folders, runtime state, events, and proposed knowledge packages."
topics: [concepts, wiki]
sources: []
---

# Concepts

The concept pages define the vocabulary a maintainer needs before changing
Yoke's harness, provider planning, folder authoring, runtime records, event
streams, or future knowledge-context boundary. Read them as a map of the
system's nouns before moving into exact CLI behavior or product integration.

## Core Runtime Vocabulary

Start with [Yoke Harness](yoke-harness). It explains the object that binds a
portable agent definition to a concrete Claude or Codex surface.

Read [Provider Surfaces](provider-surfaces) next when a change depends on
which Claude or Codex entrypoint can support a feature. That page explains why
Yoke plans against exact surfaces rather than only provider names.

Use [Runs And Sessions](runs-and-sessions) and
[Normalized Events](normalized-events) together. Runs and sessions explain the
difference between collected execution results and live conversation handles;
normalized events explain the shared stream records that connect provider
activity to stored or embedded execution state. [Runtime Flow](../architecture/runtime-flow)
connects both concepts to harness execution and `.yoke` snapshots.

## Authoring And Knowledge

[Agent Folders](agent-folders) is the entrypoint for filesystem-authored
agents, skills, subagents, workflows, and named collections. Read it before
changing folder loading, saving, CLI collection behavior, or provider lowering.

[Knowledge Packages](knowledge-packages) is intentionally future-facing. It
records the proposed split between procedural skills and reusable factual
context, and it links that product direction back to agent folders, Yoke
surface planning, and codealmanac integration.
