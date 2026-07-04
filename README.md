# Yoke

Yoke is a provider-neutral harness SDK for agent systems.

It is for people who want to build serious agents without rebuilding the agent loop.
Claude and Codex already provide powerful coding harnesses. Yoke lets you define
your agent system once, then run it on the harness you want.

```python
from pathlib import Path

from yoke import Agent, Goal, Harness, Skill

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

harness = Harness(provider="claude", agent=agent, cwd=Path.cwd())
```

The first public sketch is simple on purpose. The API is allowed to change as
we pressure-test it against Claude Agent SDK, Codex app-server, and Eve.

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

## Design references

Yoke is inspired by:

- Eve for filesystem-first authoring and discover/compile/run separation.
- Claude Agent SDK for sessions, subagents, skills, plugins, and workflows.
- Codex app-server for thread state, goals, typed events, and provider protocol.
- Cosmic Python for ports, adapters, and clean composition.

## Status

Yoke is being designed and built. The current code is a deliberately small
language seed, not a finished runtime.

The first implementation milestones are:

1. public Pydantic models
2. folder loader
3. provider ports
4. Claude adapter
5. workflow runner
6. Codex adapter
7. goals
8. CodeAlmanac integration
