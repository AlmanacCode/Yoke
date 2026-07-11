# Claude hook events have an opt-in live smoke

Date: 2026-07-04

Yoke now has an optional Claude hook smoke in `scripts/smoke_harnesses.py`:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-hooks
```

The smoke lazily imports `claude_agent_sdk.HookMatcher`, enables `ClaudeOptions(include_hook_events=True)`, registers no-op `PreToolUse` and `PostToolUse` hooks through the raw Claude options escape hatch, asks Claude to use the Read tool on `README.md`, and requires at least one normalized `Event(kind="hook")` before succeeding.

Normal readiness checks and unit tests do not import Claude SDK or require auth. Unit coverage uses a fake `claude_agent_sdk` module to verify that the smoke wires hook options correctly.

This smoke is intentionally opt-in because real Claude runs can be slow, billable, and account-dependent. It is the runtime pressure test for the hook mapping work in `docs/notes/0132-claude-subagent-hook-identity.md` and `docs/notes/0133-claude-tool-hooks-carry-subagent-identity.md`.

Next pressure test: run the smoke in an authenticated Claude environment and record whether the live SDK emits hook messages with the documented shape.

## Live result on 2026-07-04

Command:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-hooks
```

Observed output:

```text
claude:claude_python_sdk: ok: Claude authenticated via claude.ai
claude_python_sdk hooks: succeeded: hooks=6 tools=1 output='yoke-claude-hooks-smoke'
```

This proves the current local Claude environment can emit hook events through the Python SDK and that Yoke's normalized event stream sees them during a real provider run. The smoke did not specifically prove subagent hook identity fields, because the prompt used a read-only `Read` tool rather than spawning a subagent.
