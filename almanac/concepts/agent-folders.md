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
  - id: cli
    type: file
    path: src/yoke/cli.py
  - id: example-folder
    type: file
    path: examples/folder_agent/
  - id: codex-skills
    type: file
    path: src/yoke/providers/codex_app/skills.py
  - id: claude-adapter
    type: file
    path: src/yoke/providers/claude.py
  - id: readiness-tests
    type: file
    path: tests/test_readiness.py
  - id: live-folder-check
    type: file
    path: examples/live_folder_features.py
  - id: live-folder-transcript
    type: conversation
    path: /Users/rohan/.claude/projects/-Users-rohan-Desktop-Projects-Yoke/a84c81d8-4810-458d-8469-fca93efc6ee0.jsonl
  - id: provider-audit
    type: file
    path: docs/provider-truth-audit-2026-07-11/worklog.md
  - id: runtime-deployment
    type: file
    path: src/yoke/providers/runtime_deployment.py
  - id: runtime-deployment-tests
    type: file
    path: tests/test_runtime_deployments.py
---

# Agent Folders

Agent folders are the filesystem form of Yoke agents. They let an agent be written as files, loaded into the same `Agent` model used by the SDK, saved back from code, and grouped into collections for CLI or app use [@readme] [@loader]. The folder format is important because it gives agent authors a readable, versionable shape for instructions, skills, subagents, workflows, tools, permissions, model hints, and goals.

## Folder shape

A single agent folder can contain `agent.yaml`, `instructions.md`, a `skills/` directory, a `subagents/` directory, and a `workflows/` directory [@loader]. The README shows the same structure as the SDK-facing form of an agent, with skills stored under `skills/<name>/SKILL.md`, subagents stored as nested agent folders, and workflows stored under `workflows/` [@readme].

The example folder follows this shape. It has an `agent.yaml`, root instructions, one packaged skill at `skills/source-grounding/SKILL.md`, a reviewer subagent under `subagents/reviewer/`, and a small workflow file under `workflows/` [@example-folder].

## Loading folders

`Agent.from_folder()` calls the loader, which reads `agent.yaml`, combines root `instructions.md` with Markdown files under `instructions/`, loads skills, recursively loads subagents, and loads workflows [@loader]. YAML fields such as `goal`, `tools`, `permissions`, `model`, `effort`, and `options` become the corresponding `Agent` fields [@loader].

Collections add one level above a single agent. A collection folder uses `yoke.yaml` with an `agents` mapping and optional `default_provider`; `Collection.from_folder()` loads that mapping, and `collection.agent(name)` loads the named agent folder [@loader]. The README uses this to select an agent such as `codealmanac` from an `agents/` folder and pass it to a [Yoke Harness](yoke-harness) [@readme]. The shell path uses the same collection boundary before creating a harness [@cli]; see [CLI And Run Storage](../reference/cli-and-run-storage) for the commands that load collection agents from folders. `codealmanac` follows this same package boundary for its build, ingest, and garden agents; see [codealmanac Integration](../architecture/codealmanac-integration).

## Saving folders

`Agent.save()` writes the same Yoke-native folder format through `yoke.folders.save` [@folders]. The writer creates `agent.yaml`, writes `instructions.md` when instructions exist, serializes skills, recursively saves subagents, and writes workflows [@folders].

The writer protects folder identity. Workflow names and step names must round-trip as path-derived names, and runtime-only SDK values are rejected unless the caller explicitly allows omitting them [@folders]. This keeps folder-authored agents portable instead of silently dropping live Python objects.

## Workflows in folders

Folders support several workflow shapes. The loader can read YAML workflows, Markdown step folders, `workflow.py` Python programs, `script.js` provider-native scripts, script paths, and native workflow names [@loader]. Portable Markdown step workflows become `Step` objects with a prompt, agent name, dependencies, optional output schema, and optional run options [@loader].

This means agent folders are not only prompt folders. They can carry the agent's orchestration shape while still staying in the same neutral Yoke model used by code [@reference]. [Workflows](workflows) explains the difference between portable step workflows and provider-native workflow artifacts.

## Provider lowering checks

Folder-authored skills and subagents cross two provider boundaries. Path-backed folder skills are provider-native on Codex app-server and Claude Python SDK: Codex app-server collects every `skills/<name>/SKILL.md` directory as a native skill root, while Claude passes skill names and plugin roots through `ClaudeAgentOptions` [@codex-skills] [@claude-adapter]. Declared subagents do not lower the same way on every surface. Readiness tests mark Codex app-server as provider-native for live collaboration-agent activity while its Yoke-declared subagents are compiled, and they mark Claude Python SDK declared subagents as native `agents` definitions with the provider `Agent` tool available [@readiness-tests].

When a folder-agent smoke fails, check the status reports before assuming the folder failed to load. `status.skills` tells whether skills are native or compiled for the selected surface, and `status.subagents` separates Yoke-declared subagents from provider-native spawned-agent activity [@readiness-tests]. This distinction matters because a Codex app-server run can emit native collaboration-agent events while the folder's declared subagent map still lowers through provider files or instructions, whereas Claude SDK declared subagents are passed as provider agent definitions [@readiness-tests] [@claude-adapter].

Do not confuse durable bundle export with runtime deployment. `agent.bundle(...).write(...)` writes provider files because the caller asked for a project export [@reference]. Live Claude SDK and Codex app-server runs instead create temporary provider projections under a `runtime_root` outside the harness working directory, then clean those files up when the owning session closes or startup fails [@runtime-deployment] [@runtime-deployment-tests]. [Runtime Flow](../architecture/runtime-flow) explains that session-scoped boundary.

Codex named-role behavior has two boundaries. Yoke can register absolute
custom-agent files through Codex configuration, and current Codex source has a
native path where `spawn_agent(agent_type=...)` loads the registered role file
[@provider-audit]. The live backend still controls whether the model can expose
or use that `agent_type` field; the July 2026 audit found that hiding the field
made role selection unavailable, while unhiding it made the endpoint reject the
reserved tool schema [@provider-audit]. Moving generated files between project
`.codex/agents`, user agents, or absolute config files does not change that
backend contract [@provider-audit].

`examples/live_folder_features.py` is the live end-to-end smoke for this boundary. It loads provider-specific folder agents, checks that the packaged skill and `folder-reviewer` subagent were loaded, verifies the requested subagent model appears in the generated provider artifact, runs the agent through Codex app-server or Claude Python SDK, and requires both proof markers in the provider output [@live-folder-check]. The July 2026 live run showed both providers returning the skill and subagent markers; Codex app-server events also reported the nested run model, while Claude events did not report an effective subagent model even though the configuration and output marker succeeded [@live-folder-transcript].

Treat a single missing Codex marker as a live-run signal, not immediate proof that folder lowering broke. In the same July 2026 run, Codex first returned the skill marker twice while all load, lowering, model, and agent-event checks passed; a Codex-only rerun returned both markers with the same expected nested model [@live-folder-transcript].
