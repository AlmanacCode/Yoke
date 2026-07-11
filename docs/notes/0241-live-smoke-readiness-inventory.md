# 0241 - Live smoke readiness inventory

Scope: inventory only. No live providers were run for this note.

## Existing smoke commands

Main entrypoint: `scripts/smoke_harnesses.py`.

Readiness-only commands:

- `PYTHONPATH=src python scripts/smoke_harnesses.py`
  - Checks readiness for `codex_cli`, `codex_app_server`, `codex_python_sdk`, and `claude_python_sdk`.
  - Does not start provider turns unless a `--run-*` flag is passed.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --json`
  - Same readiness checks, machine-readable JSON.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --json --capabilities`
  - Adds static capability reports to readiness records.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --json --capabilities`
  - Narrows readiness to Codex app-server.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:sdk --json --capabilities`
  - Narrows readiness to Codex Python SDK.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --json --capabilities`
  - Narrows readiness to Claude Python SDK.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --channel app_server --capabilities`
  - Selects app-server exposure paths; today that means Codex app-server.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --channel sdk --json`
  - Selects SDK exposure paths.
- `PYTHONPATH=src python scripts/smoke_harnesses.py --feature readable_goal --json`
  - Selects surfaces whose static profile supports the requested feature.

Opt-in live provider commands:

- Codex app-server one-shot: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server`.
- Codex app-server stream: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream`.
- Codex app-server skills: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-skills`.
- Codex app-server collaboration event smoke: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-collab`.
- Codex app-server workflow replay: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-workflow`.
- Codex app-server request handling: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-request`.
- Codex app-server native goals: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal`.
- Codex app-server goal loop: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal-loop`.
- Codex app-server rename: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-rename`.
- Codex app-server fork: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-fork`.
- Codex Python SDK one-shot: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk`.
- Codex Python SDK fork: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk-fork`.
- Claude Python SDK one-shot: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude`.
- Claude Python SDK hooks: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-hooks`.
- Claude Python SDK skills: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-skills`.
- Claude Python SDK subagents: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-subagents`.
- Claude Python SDK workflow replay: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-workflow`.
- Claude Python SDK fork: `PYTHONPATH=src python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-fork`.

## Safe without extra user input

Safe to run noninteractively:

- Readiness-only commands without any `--run-*` flag.
- Readiness filters: `--surface`, `--channel`, `--feature`.
- Reporting flags: `--json`, `--capabilities`.

Conditionally safe:

- `uv run --with openai-codex ... --json --surface codex:sdk` checks Codex SDK readiness without a provider turn, but may download/install the optional package.
- `uv run --with claude-agent-sdk ... --json --surface claude:sdk` checks Claude SDK readiness without a provider turn, but may download/install the optional package.

Not safe as automatic checks:

- Every `--run-*` flag starts at least one real provider turn or native session-control call.
- The script docstring says those operations can be slow, billable, and account-dependent.

## Credential and auth assumptions

Codex app-server:

- Readiness depends on the local `codex` CLI/app auth state.
- Existing notes record `codex login status` reporting `Logged in using ChatGPT`.
- Live coverage exists for one-shot runs, streaming, skills, collaboration events, workflows, goals, goal loop, rename, fork, and request handling.

Codex Python SDK:

- Base readiness can report missing `openai_codex` because the SDK is optional.
- Existing notes show transient readiness and one-shot success with `uv run --with openai-codex ...`.
- A local no-deps SDK install needed Yoke to pass the existing `codex` binary through SDK config when the bundled runtime was absent.
- Forking needs a persisted SDK thread; the live fix changed SDK threads away from `ephemeral=True` for the public fork contract.

Claude Python SDK:

- Base readiness can report missing `claude_agent_sdk` because the SDK is optional.
- Readiness parses `claude auth status` JSON and reports `Claude authenticated via claude.ai` when first-party Claude auth is present.
- Live smokes with `uv run --with claude-agent-sdk ...` cover one-shot runs, hooks, skills, subagents, workflows, and fork.
- Claude fork has to run start/run/fork/close in one async helper because the SDK client owns subprocess state tied to one event loop.

## Unit coverage for smoke mechanics

- `tests/test_smoke_harnesses.py` covers smoke filtering by channel, feature, and surface; readiness record shape; capability printing; and the smoke helper wiring for hooks, skills, workflows, Codex app request handling, collaboration, rename, and Claude subagents.
- `tests/test_codex_python_sdk.py` covers SDK adapter routing, missing-package readiness, event mapping, existing-Codex-binary config, run setup, fork, and interrupt wiring with fakes.
- `tests/test_codex_app_server_params.py` covers app-server initialize capabilities, typed options, request handlers, runtime-only option reporting, and exposure shape.
- `tests/test_codex_app_events.py` covers app-server event normalization for collab agent/tool calls, goals, rate limits, and unknown notifications.
- `tests/test_claude_readiness.py` covers Claude auth JSON parsing.
- `tests/test_claude_options.py` and `tests/test_claude_events.py` cover Claude SDK option lowering and event normalization.

## Next concrete smoke improvements

- Add a script-level `--list` or `--plan` mode that prints all readiness and live smoke commands without running providers. This would make the current inventory discoverable from `scripts/smoke_harnesses.py` instead of scattered notes.
- Add a Codex Python SDK live stream smoke. Unit coverage already reuses app-server event mapping and interrupt wiring, but the manual script only has SDK one-shot and SDK fork live flags.
- Add a Claude Python SDK permission-callback smoke. Existing tests cover `can_use_tool` and hooks reaching SDK options, while live Claude coverage focuses on one-shot, hooks, skills, subagents, workflow, and fork.
- Add a compact per-surface smoke matrix note after each live sweep with columns for readiness, one-shot, stream, workflow, skills, subagents/collab, request/permissions, goal, fork, and last observed command.
- Keep SDK dependency checks separate from live provider turns. The existing `uv --with ... --json --surface ...` pattern is the right low-risk gate before asking for live SDK smokes.

## Source paths

- `scripts/smoke_harnesses.py`
- `tests/test_smoke_harnesses.py`
- `tests/test_codex_python_sdk.py`
- `tests/test_codex_app_server_params.py`
- `tests/test_codex_app_events.py`
- `tests/test_claude_readiness.py`
- `tests/test_claude_options.py`
- `tests/test_claude_events.py`
- `docs/notes/0055-live-harness-smoke.md`
- `docs/notes/0112-smoke-readiness-json-is-for-agents.md`
- `docs/notes/0127-transient-sdk-live-smokes-2026-07-04.md`
- `docs/notes/0134-claude-hook-live-smoke.md`
- `docs/notes/0137-codex-app-server-request-live-smoke.md`
- `docs/notes/0149-live-codex-app-server-report-and-run-smoke.md`
- `docs/notes/0156-smoke-channel-filter.md`
- `docs/notes/0172-live-smoke-matrix-2026-07-04.md`
- `docs/notes/0173-codex-app-stream-smoke.md`
- `docs/notes/0195-live-smoke-refresh-2026-07-04.md`
- `docs/notes/0202-claude-subagent-live-smoke.md`
- `docs/notes/0213-live-portable-workflow-smoke.md`
- `docs/notes/0214-live-skill-smoke.md`
- `docs/notes/0221-live-smoke-status.md`
- `docs/notes/0222-codex-python-sdk-live-install-and-fork.md`
