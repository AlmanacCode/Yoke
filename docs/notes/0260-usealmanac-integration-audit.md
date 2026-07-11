# 0260 - usealmanac integration audit

Date: 2026-07-04

Scope: bounded read-only audit of `/Users/rohan/Desktop/Projects/usealmanac` for future Yoke integration. No code was changed. `almanac search` failed in that checkout with `hosted API returned HTTP 404`, so this uses checked-in `.almanac/pages/*.md`, repo docs, and source files as evidence.

## Short answer

Yoke's natural `usealmanac` integration point is the hosted worker execution seam, not the dashboard or GitHub delivery layer.

The lowest-risk first path is still indirect: CodeAlmanac uses Yoke internally, while `usealmanac` keeps invoking CodeAlmanac from Modal and continues receiving the same `UpdateBundle` contract. Direct `usealmanac` integration is only justified if the hosted worker needs to choose provider surfaces, inspect readiness/status reports, or expose Yoke feature support as hosted product state.

## Current runtime surfaces

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/app.py` wires a `ModalWorker` into `Updates`, then runs post-commit worker effects after GitHub webhook handling. The app root keeps the worker as an integration, not product truth.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/workers.py` loads a persisted `Run`, calls `ModalWorker.start(run)`, and records `worker_call_id`. This is the backend-side worker invocation seam.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/integrations/modal/client.py` is a thin Modal adapter around `modal.Function.from_name(...).spawn(payload)`. It does not know about agents, Codex, CodeAlmanac, or Yoke.

`/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/updates_worker.py` is the worker-side execution seam. It hydrates secrets, materializes Codex auth, checks out the source, runs CodeAlmanac, collects `.almanac` changes, posts completion, and returns an `UpdateBundle`.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/codealmanac.py` hardcodes the current agent command surface: PR runs call `codealmanac ingest github:pr:<n> --foreground --using codex -y`; branch runs call `codealmanac init --using codex -y`.

`/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/runtime.py` builds the Modal image with `codealmanac@latest` and `@openai/codex`, plus GitHub/Doppler tooling. There is no `almanac-yoke` dependency today.

`/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/model_auth.py` is a narrow Codex subscription-auth shim. It writes `CODEX_AUTH_JSON` to `~/.codex/auth.json`; missing auth becomes a blocked bundle.

`/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/commands.py` shells out through `subprocess.run(...)` and captures stdout/stderr. This is the local command-runner machinery Yoke could replace only if `usealmanac` directly owns provider execution.

## Product contracts to preserve

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/models.py` defines the durable contract: `Run`, `PullRequestSource`, `BranchSource`, `CommitToBranch`, `OpenWikiPullRequest`, and `UpdateBundle`.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/completion.py` consumes `UpdateBundle`, marks runs failed/delivered, and emits `RunDelivered`. Yoke should not own this lifecycle.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/delivery.py` is the GitHub writer. It revalidates paths and commits/opens PRs. Yoke should not write GitHub output directly.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/server/internal_router.py` exposes the shared-secret completion callback at `/api/internal/runs/complete`.

`/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/server/runs_router.py` and `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/server/dtos/runs.py` expose run history to the dashboard. Today the DTO has source/status/summary/files/commit timing, not provider-surface metadata.

The checked-in wiki pages `/Users/rohan/Desktop/Projects/usealmanac/.almanac/pages/modal-update-worker.md`, `/Users/rohan/Desktop/Projects/usealmanac/.almanac/pages/update-bundle-contract.md`, and `/Users/rohan/Desktop/Projects/usealmanac/.almanac/pages/update-source-boundary.md` all reinforce the same boundary: worker runs the brain, backend owns delivery, no generic source framework yet.

## Likely future integration slice

If integration stays indirect through CodeAlmanac, `usealmanac` may only need compatibility updates around:

- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/runtime.py` if the Modal image must install a CodeAlmanac version that depends on `almanac-yoke` or provider extras.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/codealmanac.py` if `--using codex` changes to a Yoke-backed surface name or option shape.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/model_auth.py` if CodeAlmanac/Yoke moves away from the temporary Codex subscription-auth file contract.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/updates_worker.py` if CodeAlmanac starts returning richer machine-readable run metadata that should affect `UpdateBundle.summary`, `blocker`, or `error`.

If `usealmanac` integrates Yoke directly, the slice likely touches:

- `/Users/rohan/Desktop/Projects/usealmanac/backend/pyproject.toml` for `almanac-yoke` and optional provider dependencies.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/runtime.py` to install Yoke/provider runtime packages in the Modal image.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/updates_worker.py` to replace command shell-out with `yoke.Harness(...).run(...)`, while still returning `UpdateBundle`.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/model_auth.py` to become provider-surface auth materialization rather than Codex-only setup.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/models.py` only if hosted run records need first-class provider surface/runtime/status fields.
- `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/server/dtos/runs.py` and frontend run surfaces only if provider status becomes visible product state.

## Risks

Do not let Yoke own `usealmanac` product lifecycle. Yoke's own boundary says applications own jobs, retries, persistence, and mutation policy; that maps to `Updates`, `Delivery`, and run storage here.

Do not bypass backend delivery. `usealmanac` explicitly keeps GitHub writes in `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/services/updates/delivery.py`; worker-side writes would violate the strongest current invariant.

Do not add a generic source/runtime registry just because Yoke supports many surfaces. `/Users/rohan/Desktop/Projects/usealmanac/.almanac/pages/update-source-boundary.md` says new source kinds should wait for a real second source and delivery behavior.

Watch the `.almanac` root assumption. The worker still collects changes from the hosted root constant through `/Users/rohan/Desktop/Projects/usealmanac/backend/modal_app/updates_worker.py` and `/Users/rohan/Desktop/Projects/usealmanac/backend/src/almanac/core/constants.py`; prior compatibility notes flagged root drift between CodeAlmanac and usealmanac.

The current Modal image installs `codealmanac@latest` at build time. A Yoke-backed CodeAlmanac release changes the runtime dependency graph, so the future slice should pin or otherwise verify the package/runtime contract before relying on it in production.

No current `Yoke` or `yoke` references were found in `usealmanac` across backend, frontend, docs, `.almanac`, `AGENTS.md`, `MANUAL.md`, `CLAUDE.md`, and `Makefile` with `frontend/reference`, `docs/references`, lockfiles, and node modules excluded.
