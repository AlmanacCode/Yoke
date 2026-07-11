# Subagent status reports definition sources

Yoke now reports more concrete subagent metadata through `status.subagents`.

The existing support fields remain:

- `inline`
- `declared`
- `filesystem`
- `collab`

The new descriptive fields are:

- `definition_sources`: human-readable places definitions come from
- `built_in`: whether the provider has a built-in general-purpose worker shape
- `agent_tool`: whether invocation goes through Claude's Agent tool
- `events`: whether Yoke expects provider subagent activity to appear in the
  event stream

For `claude:sdk`, Yoke reports:

```text
definition_sources = ("agents_parameter", ".claude/agents")
built_in = true
agent_tool = true
events = true
```

This reflects Claude Agent SDK docs: subagents can be defined
programmatically through the `agents` parameter, loaded from `.claude/agents/`,
or invoked as the built-in general-purpose subagent. Claude recommends adding
`Agent` to `allowed_tools` when subagent invocation should auto-approve.

For `codex:app`, Yoke reports native collaboration events separately from
declared Yoke subagents:

```text
definition_sources = (".codex/agents", "compiled_instructions")
built_in = false
agent_tool = false
events = true
```

That keeps Codex app-server `collabAgentToolCall` events distinct from Claude
SDK `AgentDefinition` subagents.

Verification:

```bash
PYTHONPATH=src uv run pytest tests/test_readiness.py tests/test_capabilities.py tests/test_claude_options.py
uv run ruff check src/yoke/status.py tests/test_readiness.py
```

Observed:

```text
114 passed
All checks passed!
```

Sources:

- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/agent-sdk/python
