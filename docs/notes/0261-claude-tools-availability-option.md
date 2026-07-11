# 0261 - Claude tools availability option

Date: 2026-07-04

## Change

Yoke now exposes Claude's top-level SDK `tools` option through
`ClaudeOptions.tools`.

This is deliberately provider-specific. Yoke's neutral `Agent.tools` remains the
normal portable API for available capabilities. `ClaudeOptions.tools` exists for
callers who need Claude Agent SDK's exact tool availability contract.

## Why

Claude Agent SDK separates tool availability from tool approval:

- `tools` controls the base set of available built-in tools.
- `allowed_tools` auto-approves matching tool calls.
- `disallowed_tools` removes matching tools from use.
- `can_use_tool` only sees calls that reach an ask decision.
- `PreToolUse` hooks can observe or gate every matching tool call.

Before this slice, Yoke typed `allowed_tools` and `disallowed_tools` but did not
have a first-class `tools` field. That made the most common Claude SDK mistake
easier: treating `allowed_tools` as if it controlled availability.

## API

```python
from yoke import ClaudeOptions, ClaudeToolset, ProviderOptions, RunOptions

options = RunOptions(
    provider=ProviderOptions(
        claude=ClaudeOptions(
            tools=("Read", "Grep"),
            allowed_tools=("Read",),
        )
    )
)

preset = ClaudeOptions(tools=ClaudeToolset())
```

`ClaudeToolset()` lowers to Claude's native preset dictionary:

```python
{"type": "preset", "preset": "claude_code"}
```

If `ClaudeOptions.tools` is unset, Yoke derives Claude tools from neutral
`Agent.tools` as before.

## Files changed

- `src/yoke/options.py`
- `src/yoke/providers/claude.py`
- `src/yoke/__init__.py`
- `tests/test_claude_options.py`
- `tests/test_public_api.py`
- `docs/reference.md`

## Verification

Focused tests:

```bash
uv run pytest tests/test_claude_options.py tests/test_public_api.py tests/test_folders.py
uv run ruff check src/yoke/options.py src/yoke/providers/claude.py src/yoke/__init__.py tests/test_claude_options.py tests/test_public_api.py
```

Result: 47 tests passed; Ruff passed.

Live Claude SDK smoke:

```bash
uv run --with claude-agent-sdk python - <<'PY'
from pathlib import Path
from yoke import Agent, ClaudeOptions, Harness, ProviderOptions, RunOptions

harness = Harness(
    "claude:sdk",
    agent=Agent(instructions="You are a concise Yoke live smoke agent."),
    cwd=Path.cwd(),
)
result = harness.run_sync(
    "Use the Read tool on README.md, then reply with exactly: yoke-claude-tools-override-smoke",
    RunOptions(
        inherit_goal=False,
        max_turns=3,
        provider=ProviderOptions(
            claude=ClaudeOptions(
                tools=("Read",),
                allowed_tools=("Read",),
            )
        ),
    ),
)
print(result.status)
print(result.output)
raise SystemExit(0 if result.ok and "yoke-claude-tools-override-smoke" in (result.output or "") else 1)
PY
```

Result: succeeded; output contained `yoke-claude-tools-override-smoke`.
