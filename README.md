# Yoke

Yoke is a provider-neutral harness SDK for agent systems.

It is for people who want serious coding agents without rebuilding the agent
loop. Claude and Codex already provide powerful harnesses. Yoke lets you define
the system once, then run it on the surface that fits the job.

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

result = await (
    Harness(provider="claude", agent=agent, cwd=Path.cwd())
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

Folder agents can be loaded directly:

```python
agent = Agent.from_folder("agent")
```

The loader understands:

- `agent.yaml`
- `instructions.md`
- sorted markdown files in `instructions/`
- flat skills in `skills/*.md`
- packaged skills in `skills/<name>/SKILL.md`
- subagents in `subagents/<name>/`
- workflows in `workflows/*.yaml`

Local folder skills are parsed into `Skill(name, description, path, instructions)`.
Yoke preserves provider-native discovery when the surface supports it:

| Surface | Packaged folder skills | Inline text skills |
| --- | --- | --- |
| Claude Python SDK | local plugin root | prompt-compiled |
| Codex app-server | `skills/extraRoots/set` | prompt-compiled |
| Codex CLI | prompt-compiled | prompt-compiled |

That distinction is load-bearing. A native skill can bring supporting files,
scripts, and provider UI affordances. A prompt-compiled skill is portable text.

## Surfaces matter

Yoke does not pretend that "Claude" or "Codex" is one uniform thing.

The real shape is:

```text
provider -> surface -> features
```

Current surfaces:

| Provider | Surface | Status |
| --- | --- | --- |
| Claude | `claude_python_sdk` | real one-shot, live sessions, plugins, skills, subagents |
| Codex | `codex_cli` | real one-shot and resumable sessions |
| Codex | `codex_app_server` | sessions, typed events, native skill roots, mutable goals |

This distinction matters. Codex app-server has primitives such as mutable
thread goals that `codex exec --json` does not expose. Claude Python SDK has
live client sessions, hooks, MCP, skills, and programmatic subagents, while
filesystem settings are a separate surface.

Yoke adapters declare capabilities per surface so the SDK does not flatten
provider-specific strengths into a fake common denominator.

Events use small Yoke nouns instead of provider prose scraping. `Event` can carry
`Tool` display metadata, `Usage`, provider session ids, source thread/turn ids,
and raw provider payloads.

One important Codex app-server wrinkle: native goals require a non-ephemeral
thread. If a `Goal` is attached, Yoke starts a persistent app-server thread
instead of an ephemeral maintenance-style thread.

Yoke has built-in adapters for the common surfaces. The clean path works without
manual registration:

```python
harness = Harness(provider="codex", surface="codex_app_server", agent=agent, cwd=repo)
result = await harness.run("Use the source-grounding skill.")
```

Embedded apps can still own adapter construction explicitly:

```python
from yoke.providers import CodexAppServer

harness = harness.with_adapter(CodexAppServer(client_name="my-app"))
```

## Sessions

One-shot is the convenience path:

```python
result = await harness.run("Diagnose the failing test.")
```

Plain scripts can use the sync twin:

```python
result = harness.run_sync("Diagnose the failing test.")
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

## Workflows

Workflows are Yoke orchestration first:

```python
workflow = Workflow(
    name="review",
    steps=(
        Step(name="draft", agent="main", prompt="Draft: {input}"),
        Step(name="review", agent="reviewer", depends_on=("draft",), prompt="{draft}"),
    ),
)

result = await harness.workflow(workflow, "write release notes")
```

This is intentionally not provider-native yet. It composes provider runs and
subagents through Yoke. Eve remains the reference for a future durable workflow
runtime.

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

Current real smokes include:

- `examples/claude_run.py`
- `examples/claude_session.py`
- `examples/codex_run.py`
- `examples/codex_session.py`
- `examples/workflow_claude.py`
- `examples/folder_claude.py`
- Codex app-server one-shot and sync examples
- Claude folder skill as native local plugin
- Codex app-server folder skill as native extra root

Next milestones:

1. Deepen Codex app-server resume/thread-read behavior.
2. Tighten event mapping across Claude and Codex so UIs can render runs uniformly.
3. Durable workflow semantics inspired by Eve.
4. CodeAlmanac integration through Yoke imports once the consuming worktree is ready.
