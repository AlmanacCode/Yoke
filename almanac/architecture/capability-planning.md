---
title: "Capability Planning"
summary: "Capability planning is the harness step that turns agent and option requirements into a concrete provider surface plan before execution."
topics: [architecture, runtime, provider-surfaces]
sources:
  - id: capabilities
    type: file
    path: src/yoke/capabilities.py
  - id: surfaces
    type: file
    path: src/yoke/surfaces.py
  - id: models
    type: file
    path: src/yoke/models.py
  - id: options
    type: file
    path: src/yoke/options.py
  - id: capability-tests
    type: file
    path: tests/test_capabilities.py
---

# Capability Planning

Capability planning is the runtime check that decides whether a [Yoke Harness](../concepts/yoke-harness) can perform the requested work on one concrete [Provider Surface](../concepts/provider-surfaces). It gathers feature requirements from the agent and the selected options, resolves or validates the surface, and returns a `Plan` before provider execution starts [@models]. This makes provider differences explicit: a Codex or Claude provider name is not enough to promise streaming, callbacks, goals, workflows, or native collaboration behavior.

## Inputs To The Plan

The feature language lives in `Feature` and `Support`. Features name things Yoke can reason about, such as one-shot runs, sessions, streaming, structured output, models, permissions, request events, goals, interrupts, workflows, native workflows, skills, plugins, MCP, and collaboration-agent tools [@capabilities]. Support values are `native`, `compiled`, `emulated`, `unsupported`, and `unknown` [@capabilities].

The harness builds its required feature set from two places. Agent definitions contribute features for goals, skills, subagents, workflows, and provider options, while run, session, goal-loop, and workflow options contribute runtime requirements such as structured output, event callbacks, sessions, goals, native workflows, or provider-specific permissions [@models] [@options].

## Surface Selection

Yoke keeps a profile for each known provider surface. A profile carries the provider, surface, broad channel, runtime, capability matrix, default status, and whether this package has a runnable adapter for that surface [@capabilities] [@surfaces].

When a harness has an explicit surface, planning validates that surface against the required features and reports missing support instead of silently switching surfaces [@models]. When the surface is omitted, planning can select the best known surface for the required features, optional channel, and runnable constraint [@models] [@surfaces].

Selection ranks candidate profiles by how well they satisfy the required features and by their total capability score [@surfaces]. Tests cover the important behavior: `run_event_callbacks` selects Codex app-server or Claude Python SDK automatically, explicit unsupported Codex surfaces fail before a run starts, native Claude workflow requests can select a non-runnable TypeScript SDK profile unless `runnable=True` is required, and unsupported feature sets raise diagnostics that list considered surfaces [@capability-tests].

## Why It Matters

Planning is the guardrail between product promises and provider mechanics. [Runtime Flow](runtime-flow) explains the execution path, but capability planning is the point where Yoke decides whether that path is allowed for the selected surface.

This is why [Provider Surfaces Are First-Class](../decisions/provider-surfaces-first-class) matters in day-to-day changes. Adding a new option, workflow shape, event callback, permission mode, or provider-native behavior should update the feature requirement and capability matrix together, then add tests that prove the harness selects, validates, or rejects the intended surfaces [@options] [@surfaces] [@capability-tests].
