# 0268 - Agent collection folder contract

Date: 2026-07-04

## Decision

Yoke has one collection shape for multiple agents:

```text
agents/
  yoke.yaml
  codealmanac/
    agent.yaml
    instructions.md
  inert/
    agent.yaml
    instructions.md
  reviewer/
    agent.yaml
    instructions.md
```

The manifest is `agents/yoke.yaml`. There is no repo-root manifest, no global registry, and no alternate collection format.

## Manifest

```yaml
default_provider: codex:app
agents:
  codealmanac: codealmanac
  inert: inert
  reviewer: reviewer
```

Agent paths are strings relative to the collection folder. Yoke rejects richer per-agent mappings for now because the user explicitly chose one simple approach.

## SDK shape

```python
from yoke import Collection, Harness

collection = Collection.from_folder("agents")
agent = collection.agent("codealmanac")
harness = Harness(collection.default_provider, agent=agent, cwd=repo)
```

`Collection` is a Pydantic model with `root`, `agents`, and `default_provider`. `Collection.agent(name)` loads the selected agent folder with the existing `Agent.from_folder(...)` path.

## Why this shape

The collection organizes agents, not the whole repository. Keeping the manifest inside `agents/` makes the folder portable across repositories and deploy targets. It also prevents Yoke from becoming a repo-level project manager before it has a run store, install command, or deployment command.

## What stayed out

- No root `yoke.yaml`.
- No global named-agent registry.
- No descriptions or provider settings per agent in the collection manifest.
- No implicit install into `.codex/` or `.claude/` when loading or running.
- No CLI command was added in this slice.

## Implementation evidence

Files changed:

- `src/yoke/models.py` adds `Collection`.
- `src/yoke/loader.py` adds `COLLECTION_FILE` and `load_collection`.
- `src/yoke/__init__.py` exports `Collection`.
- `tests/test_folders.py` covers loading named agents and rejecting mapping-style entries.
- `tests/test_public_api.py` covers public export.
- `README.md` and `docs/reference.md` document only the `agents/yoke.yaml` collection approach.

Focused verification:

```bash
uv run pytest tests/test_folders.py tests/test_public_api.py
uv run ruff check src/yoke/models.py src/yoke/loader.py src/yoke/__init__.py tests/test_folders.py tests/test_public_api.py
```

Both passed.

## Next pressure

The collection format makes the next missing pieces more obvious:

1. CLI: `yoke run agents codealmanac "..."`.
2. Run store: `.yoke/runs/<id>/` should record selected collection, agent name, cwd, provider, provider session id, events, result, and usage.
3. Provider install: explicit `yoke install agents codealmanac --provider codex`, never a hidden side effect of run.
