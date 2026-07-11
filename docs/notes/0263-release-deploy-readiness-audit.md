# 0263 - Release and deploy readiness audit

Date: 2026-07-04

Scope: bounded read-only audit for whether Yoke is ready as a standalone private package/repo for CodeAlmanac to consume. No code was edited. This note is the only file written.

## Short verdict

Yoke is close to ready for private package consumption, but it is not yet fully release/deploy-ready as a standalone private GitHub dependency.

The package metadata, built artifacts, `py.typed`, optional extras, release checklist, and CodeAlmanac editable wiring are in good shape. The main missing piece is a documented private GitHub consumption path with a pinned ref and a CodeAlmanac lock/update procedure.

## Evidence read

- `/Users/rohan/Desktop/Projects/Yoke/pyproject.toml`
- `/Users/rohan/Desktop/Projects/Yoke/README.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/quickstart.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/reference.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0251-package-name-and-codealmanac-wiring.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0253-release-readiness-audit.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0254-extra-install-command-cleanup.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0256-release-hygiene-pass.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0260-usealmanac-integration-audit.md`
- `/Users/rohan/Desktop/Projects/Yoke/docs/notes/0262-codex-app-server-experimental-thread-turn-options.md`
- `/Users/rohan/Desktop/Projects/Yoke/dist/almanac_yoke-0.1.0-py3-none-any.whl`
- `/Users/rohan/Desktop/Projects/Yoke/dist/almanac_yoke-0.1.0.tar.gz`
- `/Users/rohan/Desktop/Projects/Yoke/.gitignore`
- `/Users/rohan/Desktop/Projects/Yoke/dist/.gitignore`
- `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml`
- `/Users/rohan/Desktop/Projects/codealmanac/uv.lock`

## Ready

Package identity is consistent. `/Users/rohan/Desktop/Projects/Yoke/pyproject.toml` declares `name = "almanac-yoke"` and packages `src/yoke`. The docs consistently show `pip install almanac-yoke` and `from yoke import ...`.

Release metadata is now credible for a private package. `/Users/rohan/Desktop/Projects/Yoke/pyproject.toml` has version `0.1.0`, Apache-2.0 metadata, `LICENSE.md`, project URLs, Python classifiers, and `Typing :: Typed`.

The wheel contains the typing marker. `/Users/rohan/Desktop/Projects/Yoke/dist/almanac_yoke-0.1.0-py3-none-any.whl` includes `yoke/py.typed`, and the wheel metadata exposes `Name: almanac-yoke`, `Version: 0.1.0`, and the provider extras.

Optional extras are declared. `/Users/rohan/Desktop/Projects/Yoke/pyproject.toml` has `claude`, `codex`, `all`, and `dev` extras. The built wheel metadata preserves those extras.

Smoke/release docs exist. `/Users/rohan/Desktop/Projects/Yoke/docs/release.md` lists local gates, wheel import checks, `py.typed` verification, safe readiness smoke commands, opt-in live smoke commands, and CodeAlmanac integration checks.

CodeAlmanac is wired for local/private development. `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` depends on `almanac-yoke` and maps it through `[tool.uv.sources]` to editable `../Yoke`. `/Users/rohan/Desktop/Projects/codealmanac/uv.lock` records `almanac-yoke` as editable `../Yoke`.

Build artifacts are treated as generated. `/Users/rohan/Desktop/Projects/Yoke/dist/.gitignore` ignores all files under `dist/`, and `/Users/rohan/Desktop/Projects/Yoke/docs/release.md` says to `rm -rf dist` and rebuild. That is the right expectation unless this repo intentionally starts attaching wheels to GitHub releases.

## Findings

### P1 - Private GitHub install path is not documented

Yoke has docs for future package-index install and local editable install, but I did not find a concrete private GitHub dependency recipe.

Missing examples:

```toml
almanac-yoke = { git = "ssh://git@github.com/AlmanacCode/Yoke.git", rev = "<commit-or-tag>" }
```

or the equivalent PEP 508 form:

```text
almanac-yoke @ git+ssh://git@github.com/AlmanacCode/Yoke.git@<commit-or-tag>
```

Why it matters: CodeAlmanac can consume `../Yoke` on Rohan's machine, but a standalone private package/repo needs a path that works in CI, Modal images, clean worktrees, and other developer machines without assuming a sibling checkout.

Recommended next step: add a "Private GitHub consumption" section to `/Users/rohan/Desktop/Projects/Yoke/docs/release.md` and mirror the chosen CodeAlmanac command in `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` only when switching off editable local development.

### P1 - No release tag/ref policy is recorded

The package is versioned as `0.1.0`, but the release docs do not say what Git ref CodeAlmanac should pin.

Why it matters: private GitHub package installs are safest when CodeAlmanac pins a tag or commit. Depending on a moving branch makes "CodeAlmanac consumed Yoke 0.1.0" ambiguous.

Recommended next step: decide one policy:

- Tag releases as `v0.1.0`, then pin CodeAlmanac to that tag.
- Pin CodeAlmanac to an exact commit SHA until public/package-index publishing exists.

### P1 - CodeAlmanac release path is still editable-only

`/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` currently uses:

```toml
[tool.uv.sources]
almanac-yoke = { path = "../Yoke", editable = true }
```

That is correct for fast local work, but it is not a standalone package consumption contract.

Recommended next step: before shipping a CodeAlmanac release that depends on Yoke, switch the source to a pinned Git ref or ensure the release environment vendors/provides the sibling checkout deliberately.

### P2 - No CI/release workflow was found in Yoke

I found no `.github` workflow files under `/Users/rohan/Desktop/Projects/Yoke/.github`.

Why it matters: manual release is acceptable for private use, but the repo does not yet enforce `ruff`, `pytest`, build, `twine check`, or wheel import checks before a tag.

Recommended next step: either keep manual release explicit in `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`, or add a minimal GitHub Actions workflow that runs the documented gates.

### P2 - Provider extras need a clean-install smoke before declaring deploy-ready

The extras are declared and present in wheel metadata:

- `almanac-yoke[claude]`
- `almanac-yoke[codex]`
- `almanac-yoke[all]`

I did not run clean-environment installs in this audit.

Recommended next step: run the release checklist from `/Users/rohan/Desktop/Projects/Yoke/docs/release.md` in a fresh environment, including at least:

```bash
uv run --with ./dist/almanac_yoke-0.1.0-py3-none-any.whl python - <<'PY'
import importlib.metadata as md
from pathlib import Path
from yoke import Agent, Harness
import yoke

print(md.version("almanac-yoke"))
print(Agent.__name__, Harness.__name__)
assert (Path(yoke.__file__).parent / "py.typed").exists()
PY
```

Then separately test the provider extras from the private GitHub source path once that path exists.

### P2 - README still describes package-index install as future state

`/Users/rohan/Desktop/Projects/Yoke/README.md` and `/Users/rohan/Desktop/Projects/Yoke/docs/quickstart.md` say "Once published to a package index" before `pip install almanac-yoke`.

That is honest today. It means the standalone private-repo install story should be documented separately, not hidden under package-index language.

Recommended next step: keep the package-index wording, but add a private GitHub install block above it.

### P3 - Release artifacts are present locally but intentionally ignored

`/Users/rohan/Desktop/Projects/Yoke/dist/almanac_yoke-0.1.0-py3-none-any.whl` and `/Users/rohan/Desktop/Projects/Yoke/dist/almanac_yoke-0.1.0.tar.gz` exist locally. `/Users/rohan/Desktop/Projects/Yoke/dist/.gitignore` ignores them.

This is fine if releases rebuild artifacts or attach them to GitHub releases. It is not fine if another repo expects to install from committed `dist/`.

Recommended next step: state the artifact policy in `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`: `dist/` is disposable local output; consumers install from Git refs or package indexes, not committed wheels.

## Minimum checklist before CodeAlmanac consumes Yoke as standalone private repo

1. Add a private GitHub install section to `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`.
2. Choose a pinning policy: release tag such as `v0.1.0` or exact commit SHA.
3. Update `/Users/rohan/Desktop/Projects/codealmanac/pyproject.toml` from editable `../Yoke` to the chosen private Git source only when leaving local development mode.
4. Refresh `/Users/rohan/Desktop/Projects/codealmanac/uv.lock` after that source change.
5. Run Yoke's documented release gates from `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`.
6. Run CodeAlmanac's Yoke integration smoke from `/Users/rohan/Desktop/Projects/Yoke/docs/release.md`.
7. Decide whether manual release is enough or add a `.github/workflows` gate before tagging.

## Bottom line

Yoke is ready as a private local/editable package for CodeAlmanac today.

Yoke needs one more release-handoff slice before it is ready as a standalone private GitHub package dependency: document and pin the private GitHub install path, then refresh CodeAlmanac against that path.
