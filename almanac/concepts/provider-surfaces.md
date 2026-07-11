---
title: "Provider Surfaces"
summary: "Provider surfaces are concrete Claude or Codex entrypoints whose capabilities form Yoke's feature boundary."
topics: [concepts, architecture]
sources:
  - id: models
    type: file
    path: src/yoke/models.py
  - id: surfaces
    type: file
    path: src/yoke/surfaces.py
  - id: capabilities
    type: file
    path: src/yoke/capabilities.py
  - id: decision
    type: file
    path: docs/notes/0175-provider-surfaces-are-first-class.md
---

Provider surfaces are the concrete Claude or Codex entrypoints that Yoke plans against. A provider is the family, such as `codex` or `claude`; a surface is the actual exposure path, such as `codex_app_server`, `codex_python_sdk`, `codex_cli`, or `claude_python_sdk` [@models]. Surfaces matter because Yoke treats features as surface-specific, not provider-wide [@decision].

## The feature boundary

The decision note says Yoke must not treat `provider="codex"` or `provider="claude"` as enough information to know what features exist, because the same provider exposes different capabilities through different surfaces [@decision]. The code reflects this in the `Surface` enum and in the capability matrix functions that resolve, report, rank, and select surface profiles [@models] [@surfaces].

A surface profile carries provider, surface, channel, runtime, capabilities, default status, and whether this Yoke package can run it [@capabilities]. That profile is the unit used by status reports, explanations, feature checks, and automatic selection.

## How Yoke selects a surface

Yoke accepts exact surfaces, friendly aliases, and compact provider specs. For example, `codex:app` resolves to `codex_app_server`, while `claude:sdk` resolves to `claude_python_sdk` [@models]. These aliases are input sugar. Yoke still reports exact surface names in plans, runs, sessions, readiness, and events [@decision].

When no explicit surface is set, `profile_for` uses provider defaults, and `select_profile` can choose the best known surface for required features and an optional channel [@surfaces]. If a surface is explicit, harness planning validates that surface instead of silently switching it [@models].

## Capabilities and support levels

Capabilities are expressed as features with support levels. The `Feature` enum includes one-shot runs, sessions, streaming, structured output, model listing, login, permissions, request events, subagents, skills, plugins, hooks, MCP, goals, interrupts, forks, workflows, native workflows, and experimental APIs [@capabilities].

Each feature has a support value: `native`, `compiled`, `emulated`, `unsupported`, or `unknown` [@capabilities]. Reports can also include notes, lowering descriptions, recipes, and evidence for a feature on a surface [@surfaces].

## Why this is not just configuration

Provider surfaces are not a cosmetic naming scheme. They control whether a [Yoke Harness](yoke-harness) may run, stream, resume, fork, use workflows, expose request callbacks, or report a feature as unavailable. The capability matrix answers what the surface can do before the provider turn starts [@surfaces].

This is why the decision note calls provider surfaces first-class. A generic provider default is acceptable for simple use, but advanced behavior must resolve to a concrete surface before Yoke claims that a feature exists [@decision].
