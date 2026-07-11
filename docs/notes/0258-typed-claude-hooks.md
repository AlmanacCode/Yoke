# 0258 - Typed Claude hooks

Date: 2026-07-04

## Change

Yoke now exposes typed hook values:

```python
from yoke import Hook, HookEvent

Hook(
    HookEvent.PRE_TOOL_USE,
    matcher="Bash",
    callbacks=(block_dangerous_shell,),
    timeout=5,
)
```

`ClaudeOptions(hooks=(...))` lowers these values to Claude's native
`dict[HookEvent, list[HookMatcher]]` shape. Raw Claude hook dictionaries still
pass through unchanged.

## Why

Claude's Python SDK exposes hooks through `ClaudeAgentOptions.hooks`, keyed by
hook event name, with values made of `HookMatcher(matcher, hooks, timeout)`.
The local reference is:

- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/src/claude_agent_sdk/types.py`
- `/Users/rohan/Desktop/Projects/claude-agent-sdk-python/examples/hooks.py`

Yoke previously accepted raw hook dictionaries only. That worked, but it made
users know Claude's exact SDK object shape. `Hook` gives Yoke users a small
Pydantic-native front door while still delegating to Claude's native mechanics.

## Boundary

Hook callbacks are live Python callables. They do not round-trip through Yoke
folders.

`ClaudeOptions.hooks` remains runtime-only, so `agent.save(...)` rejects agents
or workflows that contain live hooks unless the caller explicitly passes
`allow_runtime_only=True`.

This keeps folder authoring honest: folders can define agents, skills,
subagents, workflows, goals, and serializable request policies, but Python
callbacks stay in SDK code.

## Verification

Focused tests:

```bash
uv run pytest \
  tests/test_claude_options.py \
  tests/test_public_api.py \
  tests/test_folders.py \
  tests/test_capabilities.py
```

Result:

```text
136 passed
```

Ruff:

```bash
uv run ruff check \
  src/yoke/options.py \
  src/yoke/providers/claude.py \
  src/yoke/__init__.py \
  tests/test_claude_options.py \
  tests/test_public_api.py
```

Result:

```text
All checks passed!
```

## Remaining work

Codex app-server has a separate hook discovery surface (`hooks/list`) and a
different request/event model. Yoke should not force that into the same
`Hook` shape until there is a concrete cross-provider operation to expose.
