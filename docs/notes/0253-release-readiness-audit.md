# 0253 - Release readiness audit after `almanac-yoke` rename

Date: 2026-07-04

## Scope

This audit only read:

- `pyproject.toml`
- `README.md`
- `docs/quickstart.md`
- `docs/reference.md`
- `docs/notes/0251-package-name-and-codealmanac-wiring.md`
- `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml`

No code was edited or verified during this audit.

## Verdict

Yoke is ready for private source usage by CodeAlmanac and private GitHub
consumers that can install from the repository. It is not ready for a public
PyPI release without a small packaging and docs pass.

## Ready for private GitHub usage

The rename is consistent for private usage. `pyproject.toml` declares the
distribution as `almanac-yoke`, while the wheel still packages `src/yoke`.
The public Python import remains:

```python
from yoke import Agent, Harness
```

The docs are honest about that split. `README.md` and `docs/quickstart.md`
both say the distribution is `almanac-yoke` and the import package is `yoke`.
`docs/reference.md` uses `from yoke import ...`, which is the right API-level
spelling.

CodeAlmanac is wired for private development. Its `pyproject.toml` depends on
`almanac-yoke`, and `[tool.uv.sources]` maps that dependency to editable
`../Yoke`. Note 0251 also records successful wheel import, editable
CodeAlmanac import, and targeted adapter tests after the rename.

## Blocks for PyPI or public release

`version = "0.0.0"` is not a real release version. Pick the first public
version before publishing.

The project metadata is thin for public PyPI. `pyproject.toml` has no license
metadata, no license file declaration, no Issues/documentation URLs, and only
minimal classifiers.

The README still describes Yoke as private and early. That is accurate today,
but public release docs should add a normal install path such as
`pip install almanac-yoke` and clearly mark editable installs as development
only.

The README status section explicitly lists `public repository/release hygiene`
as not final. That should be resolved or narrowed before public release.

The docs claim the package ships `py.typed`, but this audit did not inspect
package contents. The release check must verify that `py.typed` is present in
the built wheel.

Optional provider dependencies should be resolved in a clean environment before
release. The package exposes `claude`, `codex`, and `all` extras, and public
users will hit those names directly.

## Naming honesty

The current docs are honest. They do not tell users to `import almanac_yoke` or
`import almanac-yoke`. They consistently present:

- distribution/package install name: `almanac-yoke`
- Python import package: `yoke`
- wheel artifact spelling: `almanac_yoke-...whl`

The only docs gap is audience-specific: private docs correctly teach editable
source installs, while public docs will need a PyPI install section once the
package is published.

## Verification commands before release

Run these in `/Users/rohan/Desktop/Projects/Yoke`:

```bash
uv run ruff check .
uv run pytest
uv build
```

Check the built wheel imports under the distribution name:

```bash
uv run --with ./dist/almanac_yoke-0.0.0-py3-none-any.whl python - <<'PY'
import importlib.metadata as md
from yoke import Agent, Harness

print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
PY
```

Check package metadata before upload:

```bash
uv run --with twine twine check dist/*
```

Check readiness plans without starting provider turns:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --plan
PYTHONPATH=src python scripts/smoke_harnesses.py --plan --json
PYTHONPATH=src python scripts/smoke_harnesses.py --json --capabilities
```

Run opt-in live smokes only from an account that can safely spend provider
credits:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-server
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-stream
PYTHONPATH=src uv run --with openai-codex python scripts/smoke_harnesses.py --surface codex:sdk --run-codex-sdk-stream
PYTHONPATH=src uv run --with claude-agent-sdk python scripts/smoke_harnesses.py --surface claude:sdk --run-claude-permissions
```

Run these in `/Users/rohan/Desktop/Projects/codealmanac` before declaring the
integration release-ready:

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

```bash
uv run pytest tests/test_yoke_harness_adapter.py tests/test_claude_adapter.py tests/test_codex_adapter.py
```
