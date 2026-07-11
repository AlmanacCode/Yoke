# 0250 - Docs split review

Date: 2026-07-04

Scope: docs review only. No README, code, git, or live provider commands were changed or run. `docs/quickstart.md` and `docs/reference.md` were not present on the first read or after a light retry.

## What improved

- README now says Yoke is a private source package and explains editable local installs. That removes the public-install ambiguity from note 0246.
- README now explains model placement early: model belongs on `Agent`, `RunOptions`, or `SessionOptions`, while the harness chooses the provider surface.
- README now introduces `harness.model_selection(...)` and `harness.explain(...)` near the first-five-minutes path. That gives users a local way to ask how a run will lower without starting a provider.
- README smoke docs now point to `scripts/smoke_harnesses.py --plan` / `--list` as the safe discovery surface and include the newer Codex SDK stream and Claude permission smoke commands.
- README status now reflects recent live coverage: Claude permission callbacks, Codex app-server request handling, fork, rename, goal loop, and CodeAlmanac's editable Yoke import.

## What remains confusing

- The promised split shape is not visible yet. `docs/quickstart.md` and `docs/reference.md` are missing, so README is still the landing page, quickstart, concept guide, API reference, smoke ledger, and status page all at once.
- README is still too large for immediate usability. The first useful model/native-mechanics improvements are present, but they sit inside a long monolithic document.
- The quickstart path still reaches advanced concepts quickly: surface planning, status reports, model selection, `explain(...)`, folders, bundles, workflows, and provider-native distinctions all appear before a new user has a stable mental map.
- The workflow section still contains multiple shapes: Python program workflows, older step-DAG workflows, and provider-native script workflows. The docs say portable workflows are the default, but the reader still has to compare several APIs.
- Tracked-but-not-runnable surfaces remain in the same document as runnable beginner surfaces. That is useful for architecture, but it should live in reference docs rather than the landing page.

## Do the docs answer model, harness, and native-mechanics questions?

Partially yes.

- Model: yes. README now states model is selected by the agent or run/session options, not by the harness. It also explains that `model_selection(...)` is local and `models()` is live/provider-dependent.
- Harness: mostly yes. README continues to explain that Yoke selects exact provider surfaces and that `Harness("codex:app", ...)` and `Harness("claude:sdk", ...)` are the v1 defaults worth starting with.
- Native mechanics: yes for advanced readers. `harness.explain(...)`, capability reports, status reports, support levels, and recent smoke notes give the right answer shape: native, compiled, emulated, unsupported, or unknown. The issue is discoverability, not absence.
- Immediate usability: not yet. A new user still needs a short path that says: install locally, pick Codex app-server or Claude SDK, check readiness, run one prompt, then use `explain(...)` only when behavior is surprising.

## Next highest-impact docs change

Create the actual split files and shrink README around them.

Recommended shape:

- `README.md`: one-page landing page with value proposition, install status, two runnable examples, readiness check, and links.
- `docs/quickstart.md`: copy-paste path for Codex app-server and Claude Python SDK, including prerequisites and expected readiness failures.
- `docs/reference.md`: surfaces, capabilities, model selection, `explain(...)`, sessions, workflows, provider options, smoke matrix, and tracked-but-not-runnable surfaces.

After that split, remove duplicate long-form sections from README instead of keeping all content in both places.

## Source paths

- `README.md`
- `docs/quickstart.md` missing
- `docs/reference.md` missing
- `docs/notes/0246-readme-api-usability-critique.md`
- `docs/notes/0249-explain-api-native-mechanics.md`
