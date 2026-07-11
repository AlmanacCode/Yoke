# Yoke release checklist

Yoke is public on PyPI under the distribution name `almanac-yoke`; Python code
imports `yoke`.

## Pre-release checks

Run from the Yoke repository root:

```bash
uv run ruff check .
uv run pytest
rm -rf dist
uv build
uv run --with twine twine check dist/*
```

Verify the built wheel exposes the expected distribution and import package:

```bash
uv run --with ./dist/almanac_yoke-0.1.3-py3-none-any.whl python - <<'PY'
import importlib.metadata as md
from pathlib import Path

from yoke import Agent, Harness
import yoke

print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
assert (Path(yoke.__file__).parent / "py.typed").exists()
PY
```

Verify safe readiness surfaces:

```bash
python scripts/smoke_harnesses.py --plan
python scripts/smoke_harnesses.py --plan --json
python scripts/smoke_harnesses.py --json --capabilities
```

Run live smokes only from an account where provider usage is expected:

```bash
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk-stream
uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-permissions
```

## CodeAlmanac integration check

Run from the CodeAlmanac repository root:

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
uv run pytest tests/test_yoke_harness_integration.py
```

## Release metadata

Before a public upload, confirm:

- `pyproject.toml` has the intended version.
- `LICENSE.md` is included.
- `README.md` describes both public and editable installs honestly.
- `docs/quickstart.md` keeps `almanac-yoke` as the distribution name and
  `yoke` as the import package.
- The GitHub repository visibility matches the intended release audience.
