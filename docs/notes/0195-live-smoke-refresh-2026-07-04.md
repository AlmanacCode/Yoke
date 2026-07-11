# 0195 - Live smoke refresh on 2026-07-04

This slice refreshed real local harness evidence after the status exposure and
runtime-option changes.

## Readiness

The default smoke readiness command succeeded for Codex surfaces and reported
Claude SDK as unavailable because the base Yoke dev environment does not install
the optional `claude-agent-sdk` package:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --json --capabilities
```

Observed local readiness:

- `codex_cli`: available, `Logged in using ChatGPT`
- `codex_app_server`: available, `Logged in using ChatGPT`
- `claude_python_sdk`: unavailable in the base env, `claude_agent_sdk is not installed`

The provider CLIs are authenticated:

```text
codex-cli 0.141.0
Logged in using ChatGPT
```

```text
2.1.199 (Claude Code)
loggedIn=true
authMethod=claude.ai
apiProvider=firstParty
subscriptionType=pro
```

With the optional Claude SDK dependency injected, Claude SDK readiness succeeds:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --json --capabilities
```

Observed:

```text
claude_python_sdk available=true
message='Claude authenticated via claude.ai'
```

## Live runs

Codex app-server one-shot still works:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
```

Observed:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server run: succeeded: yoke-app-smoke
```

Codex app-server request handling still works:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-request
```

Observed:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server request: succeeded: requests=1 handler_calls=1 output='yoke-codex-request-smoke'
request-smoke-file-absent
```

Codex app-server native goal set/read/clear still works:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-goal
```

Observed:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server goal: initial='Verify Yoke native app-server goals.' updated='Verify updated Yoke goal.' cleared=None
```

Claude SDK one-shot works when `claude-agent-sdk` is available:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude
```

Observed:

```text
claude:claude_python_sdk [sdk]: ok: Claude authenticated via claude.ai
claude_python_sdk run: succeeded: yoke-claude-smoke
```

Claude SDK hook events work, but the smoke needed a slightly wider turn budget.
The previous `max_turns=2` could fail after the tool call with `Reached maximum
number of turns (2)`. The smoke now uses `max_turns=4`.

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-hooks
```

Observed:

```text
claude:claude_python_sdk [sdk]: ok: Claude authenticated via claude.ai
claude_python_sdk hooks: succeeded: hooks=6 tools=3 output='yoke-claude-hooks-smoke'
```

## Implications

Yoke's current local dev dependencies intentionally keep Claude and Codex SDKs
optional. That means readiness in the base env can correctly report missing SDK
packages even when the provider CLI is authenticated. Live Claude SDK smokes
should keep using `uv run --with claude-agent-sdk ...` unless the dev extra is
installed.

The Codex app-server smoke set now covers the high-value native surface: normal
turns, client request handling, and thread goals. Claude SDK live coverage still
proves one-shot runs and hook event normalization.

References:

- <https://developers.openai.com/codex/cli/reference>
- <https://developers.openai.com/codex/app-server>
- <https://code.claude.com/docs/en/agent-sdk/python>
- <https://code.claude.com/docs/en/agent-sdk/overview>
