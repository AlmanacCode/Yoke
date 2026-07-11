# 0165 - Claude subagents enable Agent tool

## Context

Claude Agent SDK subagents are invoked through the provider's `Agent` tool. The current docs recommend programmatic subagents through the `agents` parameter and say to include `Agent` in `allowed_tools` when you want subagent invocation to proceed without a permission prompt.

Yoke already generated Claude `AgentDefinition` objects from `Agent.subagents`, but the neutral `Tools.agent` default is `False`. That meant a root Yoke agent could declare Claude subagents while the Claude adapter still omitted or disallowed the `Agent` tool.

## Yoke change

At the Claude adapter boundary, declared subagents now imply the provider `Agent` tool:

- `tools` includes `Agent` when `agent.subagents` is non-empty.
- `disallowed_tools` does not include `Agent` when `agent.subagents` is non-empty.
- `allowed_tools` includes `Agent` under auto-approval permission mode because it is built from the same Claude tool list.

The neutral `Tools.agent` default did not change. This is provider lowering: a declared Claude subagent needs the Claude `Agent` tool to be reachable.

## Provider boundary

This does not make Codex subagents equivalent to Claude subagents. Codex subagents remain explicit-prompt/provider-orchestrated activity and custom-agent filesystem configuration. Claude SDK subagents remain client-declared `AgentDefinition` values.

## Sources checked

- https://code.claude.com/docs/en/agent-sdk/subagents
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/concepts/subagents

## Verification

- `PYTHONPATH=src uv run pytest tests/test_claude_options.py` -> 9 passed.
- `uv run ruff check src/yoke/providers/claude.py tests/test_claude_options.py` -> passed.
