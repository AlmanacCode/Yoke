# 0256 - Release hygiene pass

Date: 2026-07-04

## Change

Yoke moved from private-source-only package metadata toward normal public
release hygiene:

- package version is now `0.1.0`
- package metadata declares Apache-2.0
- `LICENSE.md` is included
- PyPI classifiers and project URLs are richer
- `docs/release.md` records pre-release checks
- README and quickstart show the future public install command
  `pip install almanac-yoke`
- editable source installs remain documented as local development installs
- `uv run pytest` now works without manually setting `PYTHONPATH=src`
- `scripts/smoke_harnesses.py` now bootstraps local `src/` when run from a
  checkout
- smoke plan output now prints direct `python scripts/smoke_harnesses.py ...`
  commands instead of old `PYTHONPATH=src ...` commands

CodeAlmanac's lock was refreshed from editable `almanac-yoke` `0.0.0` to
`0.1.0`.

## Why

The release-readiness audit in note 0253 found that private source usage was
ready, but PyPI/public release hygiene was thin. The package had no real
version, no license metadata, no license file, minimal classifiers, and no
release checklist.

The verification pass also exposed two hidden usability bugs:

1. `uv run pytest` failed collection unless `PYTHONPATH=src` was set.
2. The smoke script required `PYTHONPATH=src` despite being a repo-local
   script.

Both were fixed so the documented release commands work directly.

## Verification

Yoke full local gate:

```bash
uv run ruff check .
uv run pytest
```

Result:

```text
All checks passed!
377 passed
```

Build and metadata gate:

```bash
rm -rf dist
uv build
uv run --with twine twine check dist/*
```

Result:

```text
Successfully built dist/almanac_yoke-0.1.0.tar.gz
Successfully built dist/almanac_yoke-0.1.0-py3-none-any.whl
Checking dist/almanac_yoke-0.1.0-py3-none-any.whl: PASSED
Checking dist/almanac_yoke-0.1.0.tar.gz: PASSED
```

Wheel import and typing marker:

```bash
uv run --with ./dist/almanac_yoke-0.1.0-py3-none-any.whl python - <<'PY'
import importlib.metadata as md
from pathlib import Path

from yoke import Agent, Harness
import yoke

print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
assert (Path(yoke.__file__).parent / "py.typed").exists()
print("py.typed ok")
PY
```

Result:

```text
0.1.0
Agent Harness
py.typed ok
```

Safe smoke plan:

```bash
python scripts/smoke_harnesses.py --plan --json --surface codex:sdk --surface claude:sdk
```

Result: command succeeded and emitted direct `python scripts/smoke_harnesses.py`
commands.

CodeAlmanac integration gate:

```bash
uv run python - <<'PY'
import importlib.metadata as md

from yoke import Agent, Harness
from codealmanac.integrations.harnesses import default_harness_adapters

print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
print([type(adapter).__name__ for adapter in default_harness_adapters()])
PY
```

```bash
uv run pytest tests/test_yoke_harness_adapter.py tests/test_claude_adapter.py tests/test_codex_adapter.py
```

Result:

```text
0.1.0
Agent Harness
['YokeHarnessAdapter', 'YokeHarnessAdapter']
24 passed
```

## Remaining release gaps

Yoke is still not published. A public upload still needs a deliberate GitHub
visibility/publishing decision, release credentials, and any desired release
automation.

The current release hygiene is enough for private source usage and for a future
manual PyPI upload once the user chooses to publish.
