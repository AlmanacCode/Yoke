# CodeAlmanac package identity restore

Date: 2026-07-04

The first CodeAlmanac integration gate was not harness code. `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` had been overwritten with Yoke package metadata while the rest of the checkout was still CodeAlmanac.

Evidence used to restore it:

- `README.md` identifies the package and CLI as CodeAlmanac.
- `src/codealmanac.egg-info/PKG-INFO` had `Name: codealmanac`, `Version: 0.1.13`, summary, classifiers, URLs, dependencies, and `Requires-Python: >=3.12`.
- `src/codealmanac.egg-info/entry_points.txt` had the five console scripts.
- `src/codealmanac.egg-info/requires.txt` had the runtime dependencies.
- `uv.lock` had the editable root package as `name = \"codealmanac\"` and `version = \"0.1.13\"`.

What changed in CodeAlmanac:

- Restored `[project]` metadata to `codealmanac` `0.1.13`.
- Restored package dependencies and dev extra.
- Restored console script entry points.
- Restored Hatchling build config for `src/codealmanac`.
- Restored Ruff exclusion for vendored research snapshots under `docs/research/harness-framework/sources`.
- Ran `uv lock` so the lockfile agreed with the restored metadata.

Verification:

```bash
uv lock --check
uv run python -c \"import importlib.metadata as m; d=m.metadata('codealmanac'); print(d['Name']); print(d['Version'])\"
uv run ruff check .
uv run pytest tests/test_public_contract.py tests/test_cli.py
```

Results:

- `uv lock --check` passed after lock refresh.
- Metadata reported `codealmanac` and `0.1.13`.
- Ruff passed after excluding vendored Claude SDK source snapshots from `docs/research/harness-framework/sources`.
- Focused tests passed: 84 tests.

The local environment prints a warning about an old `.venv/lib/python3.12/site-packages/codealmanac-0.1.2.dist-info` missing `RECORD`. The package still installed and tested correctly. Treat that as local environment residue, not a Yoke integration blocker.

Relayforge checkpoint failed because `DISCORD_BOT_TOKEN` is not present in the environment.

Next integration slice:

1. Add Yoke as a deliberate CodeAlmanac dependency.
2. Add a Yoke-backed `HarnessAdapter` implementation at CodeAlmanac's existing provider adapter seam.
3. Keep CodeAlmanac changed-file accounting, job ledger, run ledger, mutation policy, and lifecycle result models.
4. Start with explicit surfaces: `claude:sdk` and `codex:app`.
