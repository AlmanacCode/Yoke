# 0269 - Explicit Yoke run store

Date: 2026-07-04

## Decision

Yoke now has an explicit local run store under `.yoke/runs/`.

The store is SDK-first. Running a harness does not implicitly write files. Callers record a result when they want an inspectable snapshot:

```python
from yoke import RunStore

result = await harness.run("Review this repository.")
record = RunStore.at(".yoke").record(
    result,
    agent="codealmanac",
    collection="agents",
)
```

## Disk shape

```text
.yoke/
  runs/
    run_abc123/
      record.json
      result.json
      events.jsonl
```

`record.json` is the inspection index. It records run id, kind, creation time, provider, surface, status, cwd, agent name, collection path, provider session id, result path, events path, and event count.

`result.json` stores the provider-neutral Yoke result snapshot with volatile provider objects removed. For one-shot/session runs, normalized events are excluded from the result snapshot because they are stored separately.

`events.jsonl` stores normalized Yoke events as JSON Lines when the run has events.

## Provider storage boundary

The Yoke run store is not the provider transcript. Codex and Claude still own their native history in provider homes such as `~/.codex` and `~/.claude`. Yoke stores the provider session id so a caller can jump from `.yoke/runs/<id>/record.json` to the native provider history when needed.

## Implementation

Files changed:

- `src/yoke/store.py` adds `RunStore` and `RunRecord`.
- `src/yoke/__init__.py` exports `RunStore` and `RunRecord`.
- `tests/test_store.py` covers storing run results, event JSONL, provider handles, loading, listing, and workflow event snapshots.
- `tests/test_public_api.py` covers public exports.
- `README.md` and `docs/reference.md` document explicit run storage.

Verification:

```bash
uv run pytest tests/test_store.py tests/test_public_api.py
uv run ruff check src/yoke/store.py src/yoke/__init__.py tests/test_store.py tests/test_public_api.py
```

Both passed.

## What stayed out

- No automatic writes in `Harness.run()`.
- No CLI commands yet.
- No SQLite index yet.
- No provider-native transcript parsing.
- No deployment-specific storage backend.

## Next pressure

The next coherent user-facing slice is CLI sugar over the two primitives that now exist:

```bash
yoke run agents codealmanac "Review this repo"
yoke runs
yoke show run_abc123
yoke events run_abc123
```

That CLI should use `Collection.from_folder("agents")`, `Harness(...)`, and `RunStore.at(".yoke")` rather than adding a second configuration shape.
