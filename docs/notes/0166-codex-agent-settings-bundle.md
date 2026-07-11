# 0166 - Codex agent settings bundle

## Context

Codex custom agents are project or user TOML files under `.codex/agents/` or `~/.codex/agents/`. The current docs also describe global subagent settings under `[agents]` in the Codex config file. These settings control fan-out behavior, not an individual custom agent definition.

Yoke already compiled `Agent.subagents` into `.codex/agents/*.toml` files. It did not have a typed way to compile project-level `[agents]` settings such as concurrent thread caps or nesting depth.

## Yoke change

Yoke now exposes `CodexAgentSettings`:

```python
agent = Agent(
    instructions="Coordinate work.",
    options={
        "codex_agents": CodexAgentSettings(
            max_threads=6,
            max_depth=1,
            job_max_runtime_seconds=1800,
        )
    },
)
```

When present, `agent.bundle(provider="codex")` emits:

```text
.codex/config.toml
```

with:

```toml
[agents]
max_threads = 6
max_depth = 1
job_max_runtime_seconds = 1800
```

Camel-case dictionary input also works through `codexAgents`, `maxThreads`, `maxDepth`, and `jobMaxRuntimeSeconds`.

## Provider boundary

This is Codex-specific. Claude subagents do not use Codex `[agents]` settings; Claude programmatic subagents use SDK `AgentDefinition`, and Claude filesystem subagents live under `.claude/agents/`.

## Sources checked

- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/concepts/subagents
- https://code.claude.com/docs/en/agent-sdk/subagents

## Verification

- `PYTHONPATH=src uv run pytest tests/test_claude_options.py tests/test_codex_subagents.py tests/test_artifacts.py` -> 19 passed.
- `uv run ruff check src/yoke/providers/claude.py src/yoke/providers/codex_agents.py src/yoke/artifacts.py src/yoke/__init__.py tests/test_claude_options.py tests/test_codex_subagents.py tests/test_artifacts.py` -> passed.
