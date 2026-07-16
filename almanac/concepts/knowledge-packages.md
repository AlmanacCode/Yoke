---
title: "Knowledge Packages"
summary: "Knowledge packages are the proposed Yoke primitive for attaching reusable factual context to agents separately from skills."
topics: [concepts, authoring, integration, knowledge]
sources:
  - id: knowledge-transcript
    type: conversation
    path: /Users/rohan/.codex/sessions/2026/07/11/rollout-2026-07-11T10-52-20-019f524f-0c90-73e1-9ae9-9989348897bf.jsonl
  - id: readme
    type: file
    path: README.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: loader
    type: file
    path: src/yoke/loader.py
---

# Knowledge Packages

Knowledge packages are the proposed Yoke primitive for reusable factual context. A skill tells an agent how to perform a task; a knowledge package tells the agent what facts, policies, prior decisions, or domain material to use while performing it [@knowledge-transcript]. The separation matters because knowledge changes when reality changes, while skills change when a procedure changes [@knowledge-transcript].

## Current Boundary

The current Yoke `Agent` model includes instructions, goals, tools, permissions, skills, subagents, workflows, model hints, and options, but it does not yet include a `knowledge` field [@models]. The current folder loader reads `agent.yaml`, `instructions.md`, `skills/`, `subagents/`, and `workflows/`; it does not load a `knowledge/` directory [@loader]. That means knowledge packages are a product direction, not a shipped folder contract.

## Relationship To Agent Folders

[Agent Folders](agent-folders) already provide the filesystem boundary where a future knowledge package could attach. The README shows agent folders as the portable package form for instructions, skills, subagents, and workflows [@readme]. The proposed extension keeps that boundary and adds knowledge as a sibling to skills rather than hiding domain facts inside `SKILL.md` files [@knowledge-transcript].

The design direction is that a complete agent package can declare both procedure and context: skills for reusable task behavior, knowledge packages for reusable facts, subagents for delegated roles, workflows for orchestration, and permissions for runtime boundaries [@knowledge-transcript].

## Almanac Boundary

The proposed split gives `codealmanac` and Almanac a clear role beside Yoke. Almanac can create, maintain, and validate the knowledge body, while Yoke attaches that body to an agent and lowers access onto Claude or Codex surfaces [@knowledge-transcript]. [codealmanac Integration](../architecture/codealmanac-integration) records the current product boundary that would consume this future primitive. In this model, an Almanac wiki can become a knowledge source exposed through an API or MCP boundary, while smaller knowledge bundles can be mounted as local files or searched through deterministic tools [@knowledge-transcript].

This boundary follows the same provider-neutral rule as the [Yoke Harness](yoke-harness): Yoke should report how the selected surface receives the knowledge rather than pretending every provider has a native knowledge-pack feature. A small bundle may be compiled to local files, a larger bundle may require search tools, and an Almanac wiki may require a connector or MCP server [@knowledge-transcript].

## Lifecycle Difference

Knowledge packages should not be treated as large skills. Skills are usually global or team-reusable procedure instructions, but knowledge often has organization-specific permissions, freshness requirements, and provenance requirements [@knowledge-transcript]. A future package manifest therefore needs to describe access, source, capabilities such as search and citations, and update semantics separately from skill execution [@knowledge-transcript].
