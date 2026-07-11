# 0251 - Package name and CodeAlmanac wiring

Date: 2026-07-04

## Decision

Yoke keeps the import package `yoke`, but the Python distribution is now
`almanac-yoke`.

## Why

PyPI already has a package named `yoke` at version `0.12.0`, owned by another
project. `almanac-yoke` returned a PyPI 404 during lookup on 2026-07-04, so it
is the clean publishable distribution name while preserving the public Python
API:

```python
from yoke import Agent, Harness
```

This matches the SDK design goal: the code people write should stay simple,
while packaging uses a namespace that can be owned by Almanac.

## Changes

- `Yoke` package metadata changed from `name = "yoke"` to
  `name = "almanac-yoke"`.
- CodeAlmanac now depends on `almanac-yoke` and maps it to the editable
  sibling source at `../Yoke`.
- CodeAlmanac continues importing `from yoke import ...`; no product code needs
  to use the distribution name.
- README and quickstart now say the distribution is `almanac-yoke` and the
  import package is `yoke`.

## Verification

Yoke wheel build:

```bash
uv build
```

Result:

```text
Successfully built dist/almanac_yoke-0.0.0.tar.gz
Successfully built dist/almanac_yoke-0.0.0-py3-none-any.whl
```

Wheel import smoke:

```bash
uv run --with ./dist/almanac_yoke-0.0.0-py3-none-any.whl python - <<'PY'
import importlib.metadata as md
from yoke import Agent, Harness
print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
PY
```

Result:

```text
0.0.0
Agent Harness
```

CodeAlmanac editable dependency smoke:

```bash
uv run python - <<'PY'
import importlib.metadata as md
from yoke import Agent, Harness
from codealmanac.integrations.harnesses import default_harness_adapters
print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
print([type(a).__name__ for a in default_harness_adapters()])
PY
```

Result:

```text
0.0.0
Agent Harness
['YokeHarnessAdapter', 'YokeHarnessAdapter']
```

Targeted CodeAlmanac tests:

```bash
uv run pytest tests/test_yoke_harness_adapter.py tests/test_claude_adapter.py tests/test_codex_adapter.py
```

Result:

```text
24 passed
```

## Current integration state

CodeAlmanac is integrated with Yoke through an editable sibling dependency and
uses `YokeHarnessAdapter` for default Claude and Codex adapters.

`../usealmanac` has no Yoke references as of this check. That is not a blocker
for the current Yoke objective because the explicit integration target is
CodeAlmanac, but it remains a separate future integration decision if the hosted
frontend/backend needs direct harness execution.
