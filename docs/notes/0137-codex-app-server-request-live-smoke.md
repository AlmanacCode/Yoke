# Codex app-server request policy has an opt-in live smoke

Date: 2026-07-04

Yoke now has an optional Codex app-server request smoke in `scripts/smoke_harnesses.py`:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-request
```

The smoke asks Codex to try creating `.yoke-request-smoke.tmp` in the repository with read-only access and `approval=ask`. It installs `CodexAppServerOptions(request_handler=...)`, records every normalized request event passed to the handler, and returns `None` from the handler so Yoke keeps the safe default noninteractive response. The default response should decline the request, so the smoke should not create the file.

The smoke succeeds only if:

- the run succeeds,
- at least one request event is observed, and
- the `request_handler` is called.

This proves the callback wiring during a real app-server turn when Codex actually asks the client for approval/input. It intentionally does not approve commands during the smoke.

Live attempt 1 used `pwd`; Codex completed without any server request events, so the smoke now uses a safe write attempt that should need approval under read-only permissions.

## Live result on 2026-07-04

Attempt 1 used `pwd` and did not trigger a server request:

```text
codex:codex_app_server: ok: Logged in using ChatGPT
codex_app_server request: succeeded: requests=0 handler_calls=0 output='yoke-codex-request-smoke'
codex_app_server request: no server request events observed
```

The smoke was then changed to attempt creating `.yoke-request-smoke.tmp` while running with read-only access and `approval=ask`.

Command:

```bash
PYTHONPATH=src uv run python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-request
```

Observed output:

```text
codex:codex_app_server: ok: Logged in using ChatGPT
codex_app_server request: succeeded: requests=1 handler_calls=1 output='yoke-codex-request-smoke'
```

A follow-up filesystem check confirmed `.yoke-request-smoke.tmp` was absent, so the default decline response did not leave the requested file behind.
