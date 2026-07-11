# 0252 - README, quickstart, and reference split

Date: 2026-07-04

## Decision

Yoke docs now use three reader layers:

- `README.md` is the landing page.
- `docs/quickstart.md` is the copy-paste path.
- `docs/reference.md` holds the detailed API, provider, workflow, event, and
  capability material.

## Why

The README had grown to about 1,600 lines and mixed the landing page, concept
guide, quickstart, API reference, smoke ledger, status report, and design notes.
That made the first five minutes harder than the SDK itself.

The split keeps the short path readable while preserving the detailed material
for future provider work.

## Shape

`README.md` now covers:

- what Yoke is
- why it exists
- local install
- first five minutes
- model selection and `explain(...)`
- folder agents
- native/provider support summary
- readiness and smoke commands
- CodeAlmanac integration status
- links to deeper docs

`docs/quickstart.md` covers:

- local install
- picking `codex:app`, `codex:sdk`, or `claude:sdk`
- `model_selection(...)`
- `explain(...)`
- folder agents
- readiness and smoke coverage

`docs/reference.md` preserves the long-form material:

- embedding Yoke behind an app boundary
- skills, subagents, sessions, goals, workflows, events
- provider options
- surfaces and capabilities
- readiness
- design references

## Verification

Docs structural smoke:

```bash
python - <<'PY'
from pathlib import Path
paths = [Path("README.md"), Path("docs/quickstart.md"), Path("docs/reference.md")]
for path in paths:
    text = path.read_text()
    assert text.count("```") % 2 == 0, path
    assert text.startswith("# "), path
    print(path, text.count("\n") + 1, "lines", text.count("```"), "fences")
assert Path("README.md").read_text().count("\n") < 350
assert "## Embedding Yoke in an app" in Path("docs/reference.md").read_text()
assert "## Pick a surface" in Path("docs/quickstart.md").read_text()
print("docs split smoke passed")
PY
```

Result:

```text
README.md 260 lines 28 fences
docs/quickstart.md 143 lines 22 fences
docs/reference.md 1509 lines 174 fences
docs split smoke passed
```

API smoke:

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from yoke import Agent, Feature, Goal, Harness, RunOptions
h = Harness(
    "codex:app",
    agent=Agent(instructions="x", goal=Goal("Finish"), model="gpt-5.4"),
    cwd=Path.cwd(),
)
e = h.explain(RunOptions(model="gpt-5.4-mini"))
assert e.report(Feature.GOAL) is not None
assert Path("docs/quickstart.md").exists()
assert Path("docs/reference.md").exists()
print("docs split api smoke passed")
PY
```

Result:

```text
docs split api smoke passed
```

## Remaining risk

`docs/reference.md` is intentionally large because it preserved the detailed
README material. It should be split again later only when a natural boundary
emerges, such as separate provider, workflow, or event reference pages.
