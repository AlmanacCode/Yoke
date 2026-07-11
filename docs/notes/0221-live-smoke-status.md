# Live smoke status after folder-first workflow slice

Local auth was available for the two primary Yoke v1 surfaces:

- Codex CLI/app auth: `codex login status` -> logged in using ChatGPT.
- Claude Code auth: `claude auth status` -> logged in with first-party `claude.ai` auth.

Readiness checks reported:

- `codex:codex_app_server` available for goal, streaming, workflow, and request events.
- `claude:claude_python_sdk` available for session, streaming, workflow, and hooks.
- `codex:codex_python_sdk` missing because `openai_codex` is not installed.

Live smokes that passed:

- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-codex-app-server`
  - result: `codex_app_server run: succeeded: yoke-app-smoke`
- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-codex-app-workflow`
  - result: `first=succeeded second=succeeded cached=True records=1 output='yoke-codex-workflow-smoke'`
- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-claude`
  - result: `claude_python_sdk run: succeeded: yoke-claude-smoke`
- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-claude-workflow`
  - result: `first=succeeded second=succeeded cached=True records=1 output='yoke-claude-workflow-smoke'`

Current live-verification meaning:

Yoke's primary v1 surfaces work on this machine for one-shot runs and folder-first Python workflow programs with durable replay. Codex app-server is the verified native session/event surface. Claude Python SDK is verified for one-shot and Yoke-owned workflow orchestration, not mutable provider-native goal state.

Remaining live gaps:

- Codex Python SDK live smoke waits on installing `openai_codex` / `yoke[codex]`.
- Codex app-server native goal set/read/clear, goal_loop, fork, request approval, skill roots, and collab-agent smokes still need live runs.
- Claude hooks, skills, subagents, and fork smokes still need live runs.

## Additional native-control smokes

Codex app-server live passes:

- `--run-codex-app-stream`
  - result: stream produced provider session, warnings, tool events, text deltas, final text, context usage, and done; output contained `yoke-stream-smoke`.
- `--run-codex-app-skills`
  - result: `succeeded: output='yoke-codex-skill-smoke'`
- `--run-codex-app-collab`
  - result: `succeeded: agent_events=4 output='yoke-codex-collab-subagent-smoke'`
- `--run-codex-app-goal`
  - result: initial goal set, updated goal read back, clear returned `None`.
- `--run-codex-app-goal-loop`
  - result: returned provider session handle with expected goal and `auto_continues=True`.
- `--run-codex-app-rename`
  - result: title read back as `Yoke smoke rename`.
- `--run-codex-app-fork`
  - result: fork returned a distinct thread id.

Codex app-server request-event smoke remains unresolved:

- The first request smoke auto-declined a write command and could hang because the model kept working after denial.
- The smoke was changed to approve a harmless print command through `Response.allow()`.
- The live model still replied with `yoke-codex-request-smoke` without using a shell tool, so no request event or handler call was observed.
- This does not currently contradict adapter support because unit coverage exercises server request mapping and response lowering; it means the live smoke prompt is not a reliable trigger for request events.

Claude SDK live passes:

- `--run-claude-hooks`
  - result: `succeeded: hooks=6 tools=3 output='yoke-claude-hooks-smoke'`
- `--run-claude-skills`
  - result: `succeeded: output='yoke-claude-skill-smoke'`
- `--run-claude-subagents`
  - result: `succeeded: agent_events=2` and output contained `yoke-claude-subagent-smoke`.
- `--run-claude-fork`
  - first attempt exposed an event-loop bug in the smoke script: live Claude SDK clients cannot be started, run, forked, and closed through separate sync wrappers because the subprocess transport belongs to one asyncio loop.
  - the smoke now runs start/run/fork/close inside one async helper.
  - result after fix: `claude_python_sdk fork: source=<provider-session-id> fork=<new-yoke-session-id>`.

Verification after smoke fixes:

- `PYTHONPATH=src uv run pytest tests/test_smoke_harnesses.py` -> 22 passed
- `uv run ruff check scripts/smoke_harnesses.py tests/test_smoke_harnesses.py` -> all checks passed

## Request-event smoke resolved

The original Codex app-server request-event live smoke was prompt-dependent. A read-only shell command could complete without an approval request, and the model could also shortcut hard-coded markers.

The smoke now creates a random marker file whose contents are not included in the prompt. The requested shell command reads that marker, writes it to a second temporary output file, and prints it. The write side effect forces an approval request while remaining harmless and cleaned up afterward. The handler returns `Response.allow()` for shell requests.

Live result:

- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-codex-app-request`
- result: `codex_app_server request: succeeded: requests=1 handler_calls=1 output='yoke-codex-request-smoke-...'`
- result: `codex_app_server request: approved-smoke-command`

Verification after smoke fix:

- `PYTHONPATH=src uv run pytest tests/test_smoke_harnesses.py::test_codex_app_request_smoke_uses_request_handler` -> 1 passed
- `uv run ruff check scripts/smoke_harnesses.py tests/test_smoke_harnesses.py` -> all checks passed
