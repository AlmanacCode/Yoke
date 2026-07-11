---
title: "Agent Folders"
summary: "Agent folders are Yoke's filesystem format for authoring portable agents, skills, subagents, workflows, and named collections."
topics: [concepts, authoring]
sources:
  - id: readme
    type: file
    path: README.md
  - id: reference
    type: file
    path: docs/reference.md
  - id: loader
    type: file
    path: src/yoke/loader.py
  - id: folders
    type: file
    path: src/yoke/folders.py
  - id: example-folder
    type: file
    path: examples/folder_agent/
---

Agent folders are the filesystem form of Yoke agents. They let an agent be written as files, loaded into the same `Agent` model used by the SDK, saved back from code, and grouped into collections for CLI or app use [@readme] [@loader]. The folder format is important because it gives agent authors a readable, versionable shape for instructions, skills, subagents, workflows, tools, permissions, model hints, and goals.

## Folder shape

A single agent folder can contain `agent.yaml`, `instructions.md`, a `skills/` directory, a `subagents/` directory, and a `workflows/` directory [@loader]. The README shows the same structure as the SDK-facing form of an agent, with skills stored under `skills/<name>/SKILL.md`, subagents stored as nested agent folders, and workflows stored under `workflows/` [@readme].

The example folder follows this shape. It has an `agent.yaml`, root instructions, one packaged skill at `skills/source-grounding/SKILL.md`, a reviewer subagent under `subagents/reviewer/`, and a small workflow file under `workflows/` [@example-folder].

## Loading folders

`Agent.from_folder()` calls the loader, which reads `agent.yaml`, combines root `instructions.md` with Markdown files under `instructions/`, loads skills, recursively loads subagents, and loads workflows [@loader]. YAML fields such as `goal`, `tools`, `permissions`, `model`, `effort`, and `options` become the corresponding `Agent` fields [@loader].

Collections add one level above a single agent. A collection folder uses `yoke.yaml` with an `agents` mapping and optional `default_provider`; `Collection.from_folder()` loads that mapping, and `collection.agent(name)` loads the named agent folder [@loader]. The README uses this to select an agent such as `codealmanac` from an `agents/` folder and pass it to a [Yoke Harness](yoke-harness) [@readme].

## Saving folders

`Agent.save()` writes the same Yoke-native folder format through `yoke.folders.save` [@folders]. The writer creates `agent.yaml`, writes `instructions.md` when instructions exist, serializes skills, recursively saves subagents, and writes workflows [@folders].

The writer protects folder identity. Workflow names and step names must round-trip as path-derived names, and runtime-only SDK values are rejected unless the caller explicitly allows omitting them [@folders]. This keeps folder-authored agents portable instead of silently dropping live Python objects.

## Workflows in folders

Folders support several workflow shapes. The loader can read YAML workflows, Markdown step folders, `workflow.py` Python programs, `script.js` provider-native scripts, script paths, and native workflow names [@loader]. Portable Markdown step workflows become `Step` objects with a prompt, agent name, dependencies, optional output schema, and optional run options [@loader].

This means agent folders are not only prompt folders. They can carry the agent's orchestration shape while still staying in the same neutral Yoke model used by code [@reference].
