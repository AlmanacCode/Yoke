# Live smoke matrix

Date: 2026-07-04

Local readiness check:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --json
```

Result:

- `codex_cli`: available, logged in using ChatGPT.
- `codex_app_server`: available, logged in using ChatGPT.
- `codex_python_sdk`: unavailable, `openai_codex` is not installed.
- `claude_python_sdk`: unavailable, `claude_agent_sdk` is not installed.

Live turns that passed:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server run: succeeded: yoke-app-smoke
```

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:cli --run-codex-cli
codex:codex_cli [cli]: ok: Logged in using ChatGPT
codex_cli run: succeeded: yoke-smoke
```

Existing goal-loop smoke evidence from the previous slice:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal-loop
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server goal_loop: session=019f2dae-8cf7-7901-8545-e4b40a2017d4 goal='Verify Yoke goal_loop returns a provider session handle.' auto_continues=True
```

Interpretation:

Yoke has live local evidence for Codex CLI one-shot runs, Codex app-server one-shot runs, and Codex app-server goal-loop handles. Claude Python SDK and Codex Python SDK still need optional packages installed before live verification can run. Do not infer Claude SDK behavior from these Codex smokes.

Optional SDK checks with ephemeral dependencies:

```text
PYTHONPATH=src uv run --with openai-codex python scripts/smoke_harnesses.py --json --surface codex:sdk
codex_python_sdk: available, openai_codex available (0.1.0b2)
```

```text
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --json --surface claude:sdk
claude_python_sdk: available, Claude authenticated via claude.ai
```

Live SDK turns that passed:

```text
PYTHONPATH=src uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk
codex:codex_python_sdk [sdk]: ok: openai_codex available (0.1.0b2)
codex_python_sdk run: succeeded: yoke-sdk-smoke
```

```text
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude
claude:claude_python_sdk [sdk]: ok: Claude authenticated via claude.ai
claude_python_sdk run: succeeded: yoke-claude-smoke
```

Updated interpretation:

All four primary local surfaces have live smoke evidence when optional SDK dependencies are supplied ephemerally through `uv --with`: Codex CLI, Codex app-server, Codex Python SDK, and Claude Python SDK. The checkout itself still keeps SDK packages optional.

Live app-server stream that passed:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server stream: events=15 kinds=provider_session,warning,tool_use,tool_result,tool_use,tool_result,tool_use,text_delta,text_delta,text_delta,text_delta,text_delta,text,context_usage,done contains_smoke=True
```

This extends live evidence from one-shot turns to event streaming on the Codex app-server surface.
