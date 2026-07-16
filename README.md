# Yoke

<p align="center">
  <img src="https://raw.githubusercontent.com/AlmanacCode/Yoke/main/docs/assets/definition.png" alt="yoke (yōk), n. A harness that joins two, that they may pull as one. [akin to Skr. yoga, union.]" width="82%" />
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white"></a>
  <a href="https://peps.python.org/pep-0561/"><img alt="Typed" src="https://img.shields.io/badge/typed-py.typed-2b5b84"></a>
  <a href="https://claude.com/claude-code"><img alt="Claude harness" src="https://img.shields.io/badge/harness-Claude-D97757?logo=anthropic&logoColor=white"></a>
  <a href="https://openai.com/codex/"><img alt="Codex harness" src="https://img.shields.io/badge/harness-Codex-4B68F9?logo=openai&logoColor=white"></a>
  <a href="https://opencode.ai/"><img alt="OpenCode harness" src="https://img.shields.io/badge/harness-OpenCode-2f855a"></a>
  <a href="https://github.com/AlmanacCode/Yoke/blob/main/LICENSE.md"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-df7b40"></a>
</p>

**A Python SDK for building agents on Claude Code, Codex, and OpenCode.**

Claude Code, Codex, and OpenCode have become general-purpose agents: give
them instructions, skills, and subagents, and they can be shaped to any
task. Yoke lets you reuse them from code — one `Harness` that drives all
three.

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#how-it-compares">How it compares</a> ·
  <a href="#sessions">Sessions</a> ·
  <a href="#skills">Skills</a> ·
  <a href="#subagents">Subagents</a> ·
  <a href="#workflows">Workflows</a> ·
  <a href="#goals">Goals</a> ·
  <a href="#surfaces">Surfaces</a> ·
  <a href="#cli">CLI</a>
</p>

## Quickstart

```bash
pip install almanac-yoke
```

Install a provider extra when you want Yoke to manage that SDK directly:

```bash
pip install 'almanac-yoke[claude]'  # or [codex], or [all]
```

OpenCode needs no extra — it has no Python SDK to install; Yoke drives it
by spawning `opencode serve` and talking to its HTTP API directly.

Define an agent, pick a harness, run:

```python
from pathlib import Path

from yoke import Agent, Goal, Harness

agent = Agent(
    instructions="You are a careful maintainer. Make small, safe changes.",
    goal=Goal("Finish the requested implementation safely."),
)
harness = Harness("codex", agent=agent, cwd=Path.cwd())

result = await harness.run("Implement the bundle loader.")
print(result.output)
```

Swap `"codex"` for `"claude"` and the same agent runs there. Your existing
Claude Code or ChatGPT login is all it needs — no API keys. Swap it for
`"opencode"` and Yoke drives whatever provider your `opencode auth login`
(or a configured API key) already has set up.

Embedding applications can observe a one-shot run while it is happening:

```python
from yoke import RunOptions

seen = []
result = await harness.run(
    "Implement the bundle loader.",
    RunOptions(on_event=seen.append),
)

assert tuple(seen) == result.events
```

`on_event` is a synchronous callback receiving each normalized `Event` once.
It is runtime-only—it is excluded from serialized options and agent folders.
Live callback delivery is supported by the Claude Python SDK and Codex
app-server surfaces. Passing `on_event` selects one of those surfaces when the
surface is automatic, and raises `UnsupportedFeature` when an explicitly
selected surface cannot deliver callbacks. Use `harness.stream(...)` for a
portable event iterator.

## How it compares

The question that places Yoke: **who runs the agent?**

| | The agent runs in | Yoke |
| --- | --- | --- |
| [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview) · [Codex SDK](https://developers.openai.com/codex/sdk) | the lab's harness — one provider each | builds on them. They are the surfaces Yoke drives; one definition runs on both. |
| [Pydantic AI](https://ai.pydantic.dev) · [LangChain](https://www.langchain.com) | your process — a loop you assemble over model APIs | starts from a different premise: the harness already is the agent, so there is no loop to assemble. |
| [Eve](https://github.com/vercel/eve) | Eve's own durable runtime, deployed on Vercel | is closest in spirit — an agent is a directory — but compiles that directory onto Claude and Codex instead of shipping a runtime. |

## Sessions

```python
session = await harness.start()

plan = await session.run("Draft the migration plan.")
step = await session.run("Apply step one.")

await session.close()
```

State lives with the provider; Yoke holds the handle. Sessions are native on
every surface except the Codex CLI, where they work by resuming threads.

## Skills

```python
from yoke import Skill

agent = Agent(
    instructions="You are a careful maintainer.",
    skills=(Skill(path=Path("skills/source-grounding")),),
)
```

A skill is a folder with a `SKILL.md`. Claude loads skills natively, the Codex
app-server mounts them as native skill roots, and other surfaces get them
compiled to files.

## Subagents

```python
agent = Agent(
    instructions="You are a careful maintainer.",
    subagents={
        "reviewer": Agent(
            description="Find correctness and architecture risks.",
            instructions="Review concretely. Prefer file and line evidence.",
        ),
    },
)
```

A subagent is just another `Agent`. Claude runs declared subagents through its
native Agent tool. Codex app-server derives temporary custom-agent TOML and the
parent selects it with `spawn_agent(agent_type=..., fork_turns="none")`. Yoke
does not silently use a generic child: an incompatible Codex model/backend
fails honestly. Codex SDK/CLI surfaces retain their documented lowerings.

Runtime files are derived outside `cwd` and removed when the session closes.
Set `Harness(runtime_root=...)` to choose their parent cache directory. This is
different from `agent.bundle(...).write(...)`, which explicitly exports durable
provider files for a project. A later deployment reclaims runtime directories
whose owning process exited before normal cleanup.

## Workflows

```python
from yoke import Step, Workflow, WorkflowOptions

workflow = Workflow(
    name="review",
    steps=(
        Step(name="draft", agent="main", prompt="Draft release notes."),
        Step(
            name="review",
            agent="reviewer",
            depends_on=("draft",),
            prompt="Review this draft: {draft}",
        ),
    ),
)

result = await harness.workflow(
    workflow,
    options=WorkflowOptions(timeout_seconds=120, step_timeout_seconds=60),
)
```

A workflow is a small dependency graph over the agent and its subagents;
`main` is the reserved name for the root agent, and `WorkflowOptions` bounds
the run. Neither provider has a native equivalent yet, so workflows are
portable Yoke constructs — they run the same on every surface.

## Goals

```python
from yoke import Goal

session = await session.set_goal(Goal("Land the bundle loader.", token_budget=200_000))
print(await session.get_goal())
```

A goal is intent that outlives a single prompt. On the Codex app-server it is
real thread state — readable, replaceable, clearable. Everywhere else it
compiles into the provider loop, and `explain()` tells you which you got.

## No pretending

Claude and Codex expose different primitives, and Yoke does not flatten them
into a weak common denominator. The capability map is part of the API:

```python
for row in harness.explain().reports:
    print(row.feature, row.support, row.lowering)  # native, compiled, emulated, unsupported
```

| Feature | Claude SDK | Codex app-server | Codex SDK | Codex CLI |
| --- | --- | --- | --- | --- |
| Sessions | native | native | native | resume-based |
| Streaming | native | native | native transport | JSONL/process |
| Skills | native | native skill roots | compiled | files/compiled |
| Subagents | native | compiled → native tool | compiled | files/compiled |
| Goals | provider loop | native state | compiled context | provider loop |
| Workflows | portable Yoke | portable Yoke | portable Yoke | portable/limited |
| Permissions/hooks | native callbacks | native request events | sandbox/approval | flags/config |

## Agents are folders

Everything defined in Python can be saved as files, edited by hand, and loaded
back:

```python
agent.save("agent")
agent = Agent.from_folder("agent")
```

```text
agent/
  agent.yaml
  instructions.md
  skills/
    source-grounding/SKILL.md
  subagents/
    reviewer/
  workflows/
    ship/
```

Provider files like `.claude/` and `.codex/` are compiled from this source,
only when you ask:

```python
agent.bundle(provider="codex", surface="codex_cli").write(Path.cwd())
```

## Surfaces

This is the deeper layer:

```text
agent definition -> provider surface -> real harness
```

Each provider ships more than one way in. `Harness("codex")` picks the
strongest one for you (the app-server); address a surface directly when you
require an exact one:

| Surface | What it is |
| --- | --- |
| `codex:app` | Codex app-server — sessions, native goals, skill roots |
| `codex:sdk` | Codex Python SDK |
| `codex:cli` | Codex CLI — `codex exec`, resumable threads |
| `claude:sdk` | Claude Agent SDK for Python |
| `opencode:server` | OpenCode's local HTTP server — sessions, fork, native skills |

`discover` reports what this machine already has — surfaces installed, logins
ready, models available — and picks the first ready surface satisfying the
requested features:

```python
from yoke import Feature, discover

found = await discover("codex", Path.cwd(), agent)  # reuses your local login

for surface in found.surfaces:
    print(surface.surface, [model.id for model in surface.models])

harness = found.harness(Feature.STREAMING)
```

Claude also accepts runtime-only `Credentials` (redacted, never serialized);
Codex logins persist provider state, so they go through an explicit
`await harness.login(...)`.

## CLI

The same agents and folders, from the shell:

```bash
yoke run agents codealmanac "Review this repo"
yoke explain agents codealmanac
yoke status agents codealmanac
yoke install agents codealmanac --provider codex:cli
yoke runs
```

CLI runs leave inspectable snapshots under `.yoke/runs/`. SDK users can persist
returned results explicitly with `RunStore.at(".yoke/runs").record(result)`.

## Status

Yoke is an early alpha. Everything shown above is built and smoke-tested
against live providers. The API may still change before 1.0; durable workflow
execution and typed coverage of every provider-specific option remain future
work.

- [Quickstart](docs/quickstart.md)
- [Reference](docs/reference.md)
- [Design notes](docs/notes/) — every decision, recorded
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

Apache-2.0. See [LICENSE.md](LICENSE.md).
