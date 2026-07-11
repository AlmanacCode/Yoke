# 0174 - Live Codex app-server rename smoke

Yoke now has an opt-in live smoke for Codex app-server session rename:

```bash
PYTHONPATH=src python scripts/smoke_harnesses.py --surface codex:app --run-codex-app-rename
```

The smoke starts a small app-server session, calls `Session.rename_sync("Yoke smoke rename")`, checks the returned `SessionSummary.title`, and closes the session.

The first live run found a real adapter bug. `CodexAppServer._rename_thread()` reused `_rename_session()`, and `_rename_session()` always called `initialize`. A live app-server process is already initialized, so Codex returned `Codex app-server initialize: Already initialized`.

The fix made `_rename_session(..., initialize=True)` default to initializing fresh processes while `_rename_thread()` calls it with `initialize=False`.

Verified locally:

```text
codex:codex_app_server [app_server]: ok: Logged in using ChatGPT
codex_app_server rename: session=019f2d45-6f39-7430-b52b-bb204323fbd3 title='Yoke smoke rename'
```
