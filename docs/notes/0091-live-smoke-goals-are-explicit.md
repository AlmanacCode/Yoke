# 0091 - Live smoke goals are explicit

Current local readiness on 2026-07-04:

```text
codex:codex_cli: ok: Logged in using ChatGPT
codex:codex_app_server: ok: Logged in using ChatGPT
codex:codex_python_sdk: missing: openai_codex is not installed
claude:claude_python_sdk: missing: claude_agent_sdk is not installed
```

The real Codex CLI smoke passed:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-cli
codex_cli run: succeeded: yoke-smoke
```

The real Codex app-server run smoke passed:

```text
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-app-server
codex_app_server run: succeeded: yoke-app-smoke
```

Added a separate native goal smoke:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --run-codex-app-goal
```

This command checks app-server `thread/goal/set`, `thread/goal/get`, and
`thread/goal/clear` without asking the model to generate text. It stays
separate from `--run-codex-app-server` because goals are the feature that makes
app-server materially different from Codex CLI and Codex SDK surfaces.

The first live run passed:

```text
codex_app_server goal: initial='Verify Yoke native app-server goals.' updated='Verify updated Yoke goal.' cleared=None
```
