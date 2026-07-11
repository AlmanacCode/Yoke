# Claude subagent live smoke

Yoke now has an opt-in live smoke for Claude SDK subagents:

```bash
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-subagents
```

The smoke builds a root Yoke agent with a declared `readme-reviewer` subagent.
The root prompt explicitly asks Claude to use that subagent to inspect
`README.md`. The smoke requires:

- a successful Claude SDK run
- final output containing `yoke-claude-subagent-smoke`
- at least one normalized agent event, either `event.agent` or
  `event.tool.kind == ToolKind.AGENT`

Live evidence from 2026-07-04:

```text
claude:claude_python_sdk [sdk]: ok: Claude authenticated via claude.ai
claude_python_sdk subagents: succeeded: agent_events=2 output='...yoke-claude-subagent-smoke...'
```

Focused verification:

```bash
PYTHONPATH=src uv run pytest tests/test_smoke_harnesses.py tests/test_claude_options.py tests/test_claude_events.py
uv run ruff check scripts/smoke_harnesses.py tests/test_smoke_harnesses.py
```

Observed:

```text
43 passed
All checks passed!
```

Design implication: Claude SDK subagents are now covered by both static lowering
tests and a real harness smoke. This still should not be conflated with Codex
app-server collaboration events. Claude declared subagents are SDK
`AgentDefinition` values invoked through Claude's `Agent` tool; Codex app-server
collaboration events are provider-native runtime activity observed through the
app-server event stream.
