---
title: "codealmanac Integration"
summary: "codealmanac integrates with Yoke by packaging build, ingest, and garden as Yoke-native agents and keeping the product adapter thin."
topics: [architecture, integration, authoring, runtime]
sources:
  - id: integration-transcript
    type: conversation
    path: /Users/rohan/.codex/sessions/2026/07/10/rollout-2026-07-10T19-50-43-019f4f15-9750-7373-bf99-6eb61ab7ab46.jsonl
  - id: yoke-only-note
    type: file
    path: docs/notes/0264-codealmanac-yoke-only-harness-boundary.md
  - id: package-note
    type: file
    path: docs/notes/0251-package-name-and-codealmanac-wiring.md
  - id: harness-model
    type: file
    path: src/yoke/models.py
  - id: claude-options-test
    type: file
    path: tests/test_claude_options.py
  - id: codex-app-server
    type: file
    path: src/yoke/providers/codex_app_server.py
  - id: setup-transcript
    type: conversation
    path: /Users/rohan/.codex/sessions/2026/07/12/rollout-2026-07-12T00-01-58-019f5521-fafb-7321-af60-99eaaea6fbca.jsonl
  - id: codealmanac-pyproject
    type: file
    path: ../codealmanac/pyproject.toml
  - id: codealmanac-lock
    type: file
    path: ../codealmanac/uv.lock
---

# codealmanac Integration

`codealmanac` is the reference product integration for Yoke. Its durable boundary is that `codealmanac` owns wiki lifecycle work, run records, validation, and product events, while Yoke owns the agent definition, provider surface, and harness execution layer [@yoke-only-note]. The decision to keep `codealmanac` on Yoke-only harness adapters is recorded in [codealmanac Uses Yoke-Only Harness Adapters](../decisions/codealmanac-uses-yoke-only-harness-adapters). The current migration contract makes that boundary concrete: `codealmanac` uses Yoke-native packaged agents for build, ingest, and garden, and the adapter only loads an agent, binds it to a [Yoke Harness](../concepts/yoke-harness), invokes Yoke, and projects [Normalized Events](../concepts/normalized-events) and run results back into `codealmanac` lifecycle records [@integration-transcript].

## Packaged Agents Are The Boundary

`codealmanac` should treat Yoke's folder model as the agent-definition boundary. The integration contract says the product has one Yoke collection with three agent packages: `build`, `ingest`, and `garden`; each package owns `agent.yaml` and `instructions.md` [@integration-transcript]. That shape follows the [Agent Folders](../concepts/agent-folders) contract: tools, permissions, model hints, skills, subagents, and workflows live in the package files rather than in an adapter-specific manifest.

Stable instructions belong in `instructions.md`. Per-run prompts should contain only typed runtime context JSON, so the product can vary the selected source material without rebuilding the agent's stable operating procedure [@integration-transcript]. Future durable skills, subagents, and workflows should be added under the Yoke-native `skills/`, `subagents/`, and `workflows/` folders inside the relevant package [@integration-transcript].

## Adapter Responsibility

The adapter should not recreate provider orchestration in `codealmanac`. The earlier Yoke-only note removed direct Claude and Codex adapter packages from the product and kept the lifecycle path as `codealmanac -> Yoke -> Claude/Codex` [@yoke-only-note]. The final migration contract tightens the same rule: select one typed agent kind, load the packaged agent, run Yoke, and translate Yoke events/results into `codealmanac` lifecycle records [@integration-transcript]. [Runtime Flow](runtime-flow) explains the Yoke side of that execution path.

Agent selection is a required typed enum for `build`, `ingest`, or `garden` [@integration-transcript]. That keeps selection explicit while avoiding a second `codealmanac` helper-selection pipeline. Native provider behavior, including helper agents on the Codex app-server surface, remains inside the harness path instead of being duplicated in Python product code [@integration-transcript].

## Agent Knowledge Access

`codealmanac` should expose maintained knowledge to agents through the public `codealmanac` CLI first, not through a required MCP server, bundled skill, or attached script [@setup-transcript]. The proposed first-version product shape is `codealmanac setup` installing concise global agent instructions; those instructions tell shell-capable agents to run commands such as `codealmanac discover`, `codealmanac search`, and `codealmanac show` when external technical knowledge is relevant [@setup-transcript]. [Knowledge Packages](../concepts/knowledge-packages) records the related future Yoke primitive for attaching reusable factual context to agents.

This keeps the access path small: installed agent guidance points the agent to the CLI, and the CLI calls the knowledge service behind that command [@setup-transcript]. Authentication can remain in the CLI, the same path works across Codex and Claude-style shell agents, and MCP can be added later without changing the knowledge product boundary [@setup-transcript].

## Runtime Environment

Per-run environment belongs on `Harness.environment`, not in process-global mutation. The `Harness` model carries `environment` and `credentials` as excluded, non-repr runtime fields [@harness-model]. Tests assert that harness environment values override adapter environment values, stay out of `model_dump()`, and do not appear in `repr(harness)` [@claude-options-test].

Provider adapters merge this runtime state at the edge. The Codex app-server adapter combines its adapter environment with `Harness.environment` before invoking Codex commands, so product code can pass scoped variables without changing `os.environ` globally [@codex-app-server]. The integration contract records the precedence as process environment, then adapter environment, then `Harness.environment`, then typed `Harness.credentials` [@integration-transcript].

## Release Contract

`codealmanac` should depend on `almanac-yoke>=0.1.5,<0.2` for this integration shape [@integration-transcript]. Yoke's distribution name is `almanac-yoke`, while the import package remains `yoke` [@package-note]. The referenced migration verified `almanac-yoke 0.1.5` and `codealmanac 0.4.3` as the released pair, with Yoke `main` at `3d40984` and the `codealmanac` `dev` and `main` branches both at `bd4269e6` [@integration-transcript].

On July 14, 2026, the sibling `codealmanac` checkout declared `codealmanac` version `0.4.3` and depended on `almanac-yoke[claude]>=0.1.5,<0.2`; its lock resolved `almanac-yoke` to `0.1.5` [@codealmanac-pyproject] [@codealmanac-lock]. Treat that pair as the published compatibility floor recorded by this integration page, not as the newest Yoke development version.

The live proof matters because it exercised the intended boundary: a real `codealmanac` build ran through the packaged build agent and Codex app-server, created and validated 13 grounded pages, used native Codex helper agents dynamically, committed cleanly, and emitted readable normalized lifecycle events [@integration-transcript].
