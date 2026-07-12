---
title: "Yoke Harness"
summary: "Yoke Harness is the provider-neutral language that binds an agent definition to a concrete Claude or Codex surface."
topics: [concepts, architecture]
sources:
  - id: readme
    type: file
    path: README.md
  - id: reference
    type: file
    path: docs/reference.md
  - id: models
    type: file
    path: src/yoke/models.py
  - id: ports
    type: file
    path: src/yoke/ports.py
  - id: cli
    type: file
    path: src/yoke/cli.py
---

Yoke Harness is the repo's provider-neutral way to run an agent on a real coding harness. A `Harness` binds an `Agent`, a provider such as Claude or Codex, a concrete provider surface, and a working directory; it then exposes one-shot runs, sessions, streaming, workflows, status, model selection, and capability planning through one Python object [@models]. The point is not to hide provider differences. Yoke keeps provider mechanics behind adapter ports while giving product code a stable language for the parts it owns [@ports].

## Why the harness exists

Yoke starts from the idea that Claude and Codex already have useful agent loops. The README describes the shape as `agent definition -> provider surface -> real harness`, instead of building a new runtime from scratch [@readme]. The harness is the object that makes that shape executable.

This matters for app integration. The reference says product code should own product verbs, jobs, retries, safety checks, and persistence, while Yoke owns provider-neutral agent, session, and workflow values [@reference]. Provider adapters then own Claude and Codex protocol details [@ports].

## What a harness contains

The `Harness` model stores:

- `provider`, such as `claude` or `codex`
- `surface`, such as `codex_app_server` or `claude_python_sdk`
- `agent`, the portable agent definition
- `cwd`, the working directory
- optional channel and permission metadata

The constructor accepts compact provider specs such as `codex:app`, then normalizes them into separate provider and surface fields [@models]. This keeps the public API readable while preserving exact surface names for planning and reporting.

## How it chooses behavior

The harness asks the selected provider adapter to execute work. `ProviderAdapter` defines the boundary for readiness checks, login, runs, model listing, workflows, goal loops, session listing, session reads, session starts, sends, streams, goal mutation, interruption, compaction, renaming, tagging, forking, and close operations [@ports].

Before many operations, the harness resolves required features. `run`, `stream`, `start`, `workflow`, `models`, and session-management methods all call capability planning helpers before delegating to an adapter [@models]. This is where the harness connects to [Provider Surfaces](provider-surfaces): the selected surface must support the features implied by the agent and options.

The CLI is one concrete harness caller. It loads a folder collection, creates a harness for the selected provider surface, and stores run or workflow results after execution [@cli]; see [CLI And Run Storage](../reference/cli-and-run-storage) for that shell contract.

## Relationship to agents and sessions

A harness is not itself an agent. The agent is the portable definition: instructions, tools, permissions, skills, subagents, workflows, model preference, and goal metadata [@models]. A harness is also not itself a live conversation. Live conversation state is represented by `Session`, while the harness starts or resumes sessions and sends turns through the provider adapter [@models]. See [Runs And Sessions](runs-and-sessions) for that distinction.

## What it prevents

The harness prevents product code from importing provider SDK objects as its main abstraction. The reference shows a product-facing `HarnessTask` model that turns app inputs into `Agent`, `RunOptions`, and `Harness("codex:app", ...)`, keeping Claude or Codex SDK objects outside the app service boundary [@reference]. [codealmanac Integration](../architecture/codealmanac-integration) is the concrete product example: `codealmanac` loads packaged Yoke agents and projects Yoke events/results instead of owning direct Claude or Codex orchestration.

It also prevents generic provider assumptions. The harness may accept a provider-level default for ergonomics, but planning and execution resolve to a concrete surface before capability checks matter [@models].
