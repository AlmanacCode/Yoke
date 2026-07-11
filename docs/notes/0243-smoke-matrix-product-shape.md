# 0243 - Smoke matrix product shape

Date: 2026-07-04

Scope: docs inventory only. No code changed and no live providers were run.

## Desired `--plan` / `--list` shape

`scripts/smoke_harnesses.py --plan` or `--list` should make the live smoke surface obvious without starting providers.

The output should be a compact matrix with one row per provider surface and one column per smoke capability. Each cell should answer three questions:

- Is this surface expected to support the capability?
- Which command proves it live?
- Is the capability unit-tested only, live-smoked, or still unproven?

Human output should stay readable in a terminal. JSON output should expose the same records for agents and CI notes.

Suggested record fields:

- `provider`: `codex` or `claude`.
- `surface`: exact Yoke surface name.
- `channel`: `cli`, `sdk`, or `app_server`.
- `readiness_command`: no-provider readiness command.
- `live_commands`: named opt-in commands for each live smoke.
- `supported_features`: static profile features from `Harness.report()`.
- `unit_coverage`: fake/unit tests that prove wiring.
- `live_status`: last known live result or `not_run`.
- `notes`: short caveats such as optional SDK package or auth dependency.

## Matrix columns we care about

| Column | Codex app-server | Codex Python SDK | Claude Python SDK | Codex CLI |
| --- | --- | --- | --- | --- |
| Readiness | `--surface codex:app` | `--surface codex:sdk` | `--surface claude:sdk` | `--surface codex:codex_cli` |
| One-shot run | `--run-codex-app-server` | `--run-codex-sdk` | `--run-claude` | `--run-codex-cli` |
| Stream | `--run-codex-app-stream` | `--run-codex-sdk-stream` | no live flag today | no live flag today |
| Skills | `--run-codex-app-skills` | no live flag today | `--run-claude-skills` | no live flag today |
| Subagents / collab | `--run-codex-app-collab` | no live flag today | `--run-claude-subagents` | no live flag today |
| Portable workflow replay | `--run-codex-app-workflow` | no live flag today | `--run-claude-workflow` | no live flag today |
| Provider-native workflow | unsupported boundary | unsupported boundary | unsupported boundary in Python SDK | unsupported boundary |
| Request / permissions | `--run-codex-app-request` | no live flag today | `--run-claude-permissions` | no live flag today |
| Goal controls | `--run-codex-app-goal`, `--run-codex-app-goal-loop` | no live flag today | no live flag today | no live flag today |
| Rename | `--run-codex-app-rename` | no live flag today | no live flag today | no live flag today |
| Fork | `--run-codex-app-fork` | `--run-codex-sdk-fork` | `--run-claude-fork` | no live flag today |
| Optional dependency | local Codex app/CLI auth | `openai-codex` package plus Codex binary/auth | `claude-agent-sdk` package plus Claude auth | local Codex CLI auth |

## Unit tests vs live smokes

Unit tests prove script mechanics, not provider truth.

Covered by unit tests:

- Surface, channel, and feature filters.
- Readiness JSON shape and capability printing.
- Hook, skill, workflow, collaboration, request, rename, and subagent helper wiring with fake harnesses.
- Native workflow unsupported boundaries in the provider adapters, per note 0242.

Still needs live smokes to prove:

- Real provider auth and optional package availability on the developer machine.
- Real event streams, hook events, approval requests, and agent/collab events.
- Real thread/session operations: goal read/write/clear, goal loop, rename, and fork.
- Real portable workflow replay and cache behavior through provider runs.
- Real SDK behavior when launched through `uv run --with ...` rather than fakes.

## Recommendation for the next slice

Ship the `--plan` / `--list` product surface as the next slice before adding more live flags. The durable win is one discoverable matrix that names every supported smoke, every unsupported gap, and the exact command to run, without triggering providers.

## Source paths

- `scripts/smoke_harnesses.py`
- `tests/test_smoke_harnesses.py`
- `docs/notes/0241-live-smoke-readiness-inventory.md`
- `docs/notes/0242-native-workflow-boundary.md`
