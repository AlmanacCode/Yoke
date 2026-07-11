# Yoke quickstart

Yoke is a Python SDK for defining one agent system and running it on real Claude
or Codex harness surfaces.

The basic shape is:

```python
from pathlib import Path

from yoke import Agent, Goal, Harness

agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish the requested implementation safely."),
)

harness = Harness("codex:app", agent=agent, cwd=Path.cwd())
result = await harness.run("Explain this repository in three bullets.")
print(result.output)
```

## Install locally

The public distribution name is `almanac-yoke`, while the import package is
`yoke`:

```bash
pip install almanac-yoke
```

For local development in this repo:

```bash
pip install -e .
```

Provider extras:

```bash
pip install -e '.[claude]'
pip install -e '.[codex]'
pip install -e '.[all]'
```

Sibling apps can point their package manager at `../Yoke`. CodeAlmanac does
this with an editable `uv` source while Yoke is still moving quickly.

## Pick a surface

Use provider aliases for the normal surfaces:

```python
Harness("codex:app", agent=agent, cwd=Path.cwd())     # Codex app-server
Harness("codex:sdk", agent=agent, cwd=Path.cwd())     # Codex Python SDK
Harness("claude:sdk", agent=agent, cwd=Path.cwd())    # Claude Python SDK
```

`Harness("codex", ...)` defaults to Codex app-server. `Harness("claude", ...)`
defaults to Claude Python SDK.

## Understand a run before running it

Model preference belongs to the agent or the specific run/session. The harness
chooses the provider surface that interprets that model.

```python
from yoke import RunOptions

agent = Agent(instructions="You are careful.", model="sonnet")
harness = Harness("claude:sdk", agent=agent, cwd=Path.cwd())

selection = harness.model_selection(RunOptions(model="opus"))
print(selection.source)       # run
print(selection.model)        # opus
print(selection.verifiable)   # False for claude_python_sdk today
```

Use `explain(...)` for the whole local lowering story:

```python
explanation = harness.explain(RunOptions(model="opus"))

print(explanation.surface)
print(explanation.model.source)

for row in explanation.reports:
    print(row.feature, row.support, row.lowering)
```

`explain(...)` does not call a provider. It tells you whether requested features
are native, compiled, emulated, unsupported, or missing on the selected surface.

## Save an agent as a folder

```python
agent.save("agent")
agent = Agent.from_folder("agent")
```

Folder shape:

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
    ship/
      workflow.py
```

The folder is Yoke source. Provider files are compiled explicitly:

```python
bundle = agent.bundle(provider="codex", surface="codex_cli")
bundle.write(Path.cwd())
```

## Check readiness and smoke coverage

Readiness does not start an agent turn:

```python
status = await harness.status()
print(status.available, status.report.key)
```

The smoke script can list safe checks and opt-in live commands:

```bash
python scripts/smoke_harnesses.py --plan
python scripts/smoke_harnesses.py --plan --json
```

Live provider checks are explicit because they can be slow, billable, and
account-dependent.

## Learn more

- `README.md` has the product overview.
- `docs/reference.md` has the full API reference.
- `docs/notes/` records provider discoveries and design decisions.
