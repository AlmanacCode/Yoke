---
title: "Provider Surfaces Are First-Class"
summary: "Yoke treats provider surfaces as the unit of capability planning because Claude and Codex expose different features through different entrypoints."
topics: [decisions, architecture, runtime, provider-surfaces]
sources:
  - id: decision-note
    type: file
    path: docs/notes/0175-provider-surfaces-are-first-class.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: surfaces
    type: file
    path: src/yoke/surfaces.py
  - id: capabilities
    type: file
    path: src/yoke/capabilities.py
---

# Provider Surfaces Are First-Class

Yoke treats provider surfaces as first-class because `provider="codex"` or
`provider="claude"` is not enough information to know which features exist. A
surface is the exact entrypoint, such as `codex_app_server`, `codex_cli`,
`codex_python_sdk`, or `claude_python_sdk`; capability planning must resolve to
that entrypoint before Yoke claims support for streaming, sessions, skills,
subagents, workflows, goals, callbacks, or structured output [@decision-note]
[@models].

## Context

The same provider family can expose different runtime powers through different
surfaces. The original decision note used Codex app-server, Codex SDK, Claude
Python SDK, Claude continuous-client behavior, Claude Code skills, and Claude
subagents as pressure cases where provider-level names would hide real feature
differences [@decision-note].

The code now reflects that boundary. `Harness`, `Session`, and normalization
helpers store provider and surface as separate values after accepting compact
input such as `codex:app` or `claude:sdk` [@models]. The surface matrix then
returns profiles, reports, support levels, lowering text, recipes, and evidence
for one concrete provider surface at a time [@surfaces] [@capabilities].

## Decision

Yoke uses provider surfaces, not providers alone, as the unit of capability
planning. Provider-level defaults may exist for convenience, but they must
resolve to a concrete surface before planning or execution depends on feature
support [@decision-note] [@surfaces].

This means callers may write compact specs such as `Harness("codex:app",
agent=agent)`, but Yoke still reports exact surface names and checks feature
support against the selected surface [@models].

## Consequences

New provider work must update the surface capability matrix instead of adding a
generic provider boolean. If a feature is native on one surface, compiled on
another, and unsupported on a third, the matrix should say that directly
[@decision-note] [@surfaces].

Concept pages can explain what provider surfaces are, while this page records
the architectural constraint. See [Provider Surfaces](../concepts/provider-surfaces)
for the current model and [Runtime Flow](../architecture/runtime-flow) for the
execution path that uses the plan.
