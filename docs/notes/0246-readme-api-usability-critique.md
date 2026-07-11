# 0246 - README/API usability critique

Date: 2026-07-04

Scope: docs critique only. No README, package, code, git, or live provider commands were changed or run.

## What a new user can understand quickly

- Yoke is a Python SDK for defining one agent system and running it on real Claude or Codex harness surfaces.
- The central product idea is clear: Yoke names the provider surface, not just the provider.
- The first snippets teach the core nouns: `Agent`, `Harness`, `RunOptions`, `Goal`, `Skill`, `Workflow`, and provider-specific options.
- The README explains the most important boundary: Yoke is a harness adapter seam, not an app's job system or durable workflow engine.
- The public package shape is broad but discoverable through `src/yoke/__init__.py`; most README symbols are exported from `yoke`.
- The smoke notes show recent investment in proving real provider behavior separately from unit tests.

## What is confusing or missing

- The README is too long for immediate adoption. A new user has to read through surface selection, app embedding, folders, skills, sessions, goals, workflows, provider options, events, readiness, and smoke commands before knowing the happy path.
- Installation is local-dev oriented: `pip install -e .` is useful for contributors, but a public user expects `pip install yoke` or a clear "not published yet" statement.
- The first five minutes do not state which provider setup must already exist before the example can work.
- The README mixes stable working APIs with tracked-but-not-runnable surfaces such as Claude TypeScript SDK and Codex TypeScript SDK. That is architecturally honest, but confusing before the user has a working run.
- Smoke documentation in the README is stale relative to notes 0243-0245. It does not surface the new `--plan` / `--list` matrix, Codex SDK stream smoke, or Claude permission smoke as the primary discovery path.
- The workflow section contains two shapes: Python program workflows and older step-DAG workflows. Both may be real, but the README does not clearly say which one a new user should start with.
- Provider-native workflow text is correct in spirit after note 0242, but the README still spends a lot of space on native workflow shapes before the user has learned the portable default.
- There is no short API stability warning near examples. Because the project is early, readers need to know which snippets are canonical and which are advanced/planning examples.

## Examples likely to drift from the exported API

These are likely drift points because the snippets depend on names not imported in the same block, advanced shapes, or recently changed smoke coverage.

- The early `select_profile(...)` example uses `select_profile` without importing it in that block. `select_profile` is exported, but the snippet as shown is not copy-paste ready.
- The `RequestPolicy` example uses `CodexAppServerOptions(policy=policy)` without importing `CodexAppServerOptions` in that block.
- The readiness smoke command list is missing the new `--plan` / `--list` product surface from note 0244.
- The readiness smoke command list is missing `--run-codex-sdk-stream` and `--run-claude-permissions`, which notes 0244 and 0245 say are now implemented and live-smoked.
- The README says Codex Python SDK streaming is built and smoke-tested, but the detailed smoke section does not show the exact transient `uv --with openai-codex ... --run-codex-sdk-stream` command.
- The README says Claude permission callbacks route through `request_handler` / `can_use_tool`, but the smoke section does not show the exact transient `uv --with claude-agent-sdk ... --run-claude-permissions` command or the live caveat from note 0245.
- The examples rely heavily on ambient variables such as `agent`, `harness`, `repo`, `thread_id`, `Summary`, `block_dangerous_shell`, and `my_handler`. That is acceptable for reference docs, but risky in a README that starts as a quickstart.
- The public export list is very large. Any README example that imports advanced report/status classes directly is more likely to drift than examples using `Agent`, `Harness`, `RunOptions`, `SessionOptions`, `WorkflowOptions`, and provider option objects.

## Five highest-impact polish changes for the next slice

1. Replace the top third with a copy-paste quickstart that has prerequisites, install mode, one Codex app-server example, one Claude SDK example, and expected failure/readiness output.
2. Split the README into "Start", "Core concepts", and "Advanced provider controls" sections, then move deep workflow/native/provider-option reference material into separate docs.
3. Make `scripts/smoke_harnesses.py --plan` / `--list` the canonical smoke discovery path in the README, and remove the hand-maintained long command inventory.
4. Add an example-lint pass for README Python blocks that checks same-block imports for exported Yoke names and catches missing imports like `select_profile` and `CodexAppServerOptions`.
5. Add a small public API table: stable beginner API, advanced but supported API, tracked/planning surfaces, and not-yet-final areas. This lets users trust the happy path without hiding the early-stage status.

## Source paths

- `README.md`
- `pyproject.toml`
- `src/yoke/__init__.py`
- `docs/notes/0243-smoke-matrix-product-shape.md`
- `docs/notes/0244-smoke-plan-and-sdk-coverage.md`
- `docs/notes/0245-live-sdk-stream-and-claude-permission-smokes.md`
