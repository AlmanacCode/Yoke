# Yoke

Yoke is a provider-neutral harness SDK for agent systems.

It is for people who want serious coding agents without rebuilding the agent
loop. Claude and Codex already provide powerful harnesses. Yoke lets you define
the system once, then run it on the surface that fits the job.

```python
from pathlib import Path

from yoke import Agent, Goal, Harness, Skill
from yoke.providers import Claude

agent = Agent(
    instructions="You are a careful maintainer. Make small, safe changes.",
    goal=Goal(objective="Finish the requested implementation safely."),
    skills=(Skill(path=Path("skills/source-grounding")),),
    subagents={
        "reviewer": Agent(
            description="Find correctness and architecture risks.",
            instructions="Review concretely. Prefer file and line evidence.",
        ),
    },
)

result = await (
    Harness(provider="claude", agent=agent, cwd=Path.cwd())
    .with_adapter(Claude())
    .run("Implement the bundle loader.")
)
```

The API is still allowed to change. Yoke is being pressure-tested against real
Claude and Codex harnesses as it grows.

## Why Yoke?

Most agent libraries help you create a new agent runtime. Yoke takes another
path:

> define the system, then yoke it to Claude or Codex.

Yoke aims to support:

- agents
- skills
- subagents
- workflows
- goals
- sessions
- event streams
- provider-specific strengths

Without forcing Claude and Codex into a weak fake common denominator.

## SDK and folder parity

Yoke should feel natural in Python:

```python
Agent(
    instructions="...",
    skills=(Skill(path=Path("skills/source-grounding")),),
    subagents={"reviewer": Agent(description="...", instructions="...")},
)
```

And natural as a folder:

```text
agent/
  agent.yaml
  instructions.md
  skills/
    source-grounding/SKILL.md
  subagents/
    reviewer/
      agent.yaml
      instructions.md
  workflows/
```

Neither form should be a second-class export of the other.

## Surfaces matter

Yoke does not pretend that "Claude" or "Codex" is one uniform thing.

The real shape is:

```text
provider -> surface -> features
```

Current surfaces:

| Provider | Surface | Status |
| --- | --- | --- |
| Claude | `claude_python_sdk` | real one-shot and live sessions |
| Codex | `codex_cli` | real one-shot and resumable sessions |
| Codex | `codex_app_server` | researched; future richer adapter |

This distinction matters. Codex app-server has primitives such as mutable
thread goals that `codex exec --json` does not expose. Claude Python SDK has
live client sessions, hooks, MCP, skills, and programmatic subagents, while
filesystem settings are a separate surface.

Yoke adapters declare capabilities per surface so the SDK does not flatten
provider-specific strengths into a fake common denominator.

## Sessions

One-shot is the convenience path:

```python
result = await harness.run("Diagnose the failing test.")
```

Sessions are the multi-turn path:

```python
session = await harness.start()
try:
    first = await session.run("Remember the word yoke.")
    second = await session.run("What word did I ask you to remember?")
finally:
    await session.close()
```

Claude sessions are live SDK clients. Codex CLI sessions are persisted thread
ids resumed through `codex exec resume`.

Both paths have been smoke-tested against real local harnesses.

## Design references

Yoke is inspired by:

- Eve for filesystem-first authoring and discover/compile/run separation.
- Claude Agent SDK for sessions, subagents, skills, hooks, MCP, plugins, and task budgets.
- Codex CLI/SDK for exec JSONL, resumable threads, and structured output.
- Codex app-server for thread state, goals, typed events, and richer app protocol.
- Cosmic Python for ports, adapters, and clean composition.

## Status

Yoke is being designed and built. The current code is an early runtime, not a
finished framework.

Current real smokes:

- `examples/claude_run.py`
- `examples/claude_session.py`
- `examples/codex_run.py`
- `examples/codex_session.py`

Next milestones:

1. Codex app-server surface research and adapter skeleton.
2. Workflow runner shaped by Claude/Eve/Codex reality.
3. Deeper skills and filesystem authoring.
4. Native/mutable goals where the surface supports them.
5. CodeAlmanac integration through Yoke imports.
