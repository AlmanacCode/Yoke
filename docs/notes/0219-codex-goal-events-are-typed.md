# Codex app-server goal events carry typed Goal state

Codex app-server exposes mutable thread goal state through `thread/goal/set`, `thread/goal/get`, and `thread/goal/clear`, and it also emits `thread/goal/updated` / `thread/goal/cleared` notifications while a turn stream is active.

Yoke maps that stream into provider-neutral `Event` objects. `Event.goal` now carries the parsed `Goal` for `thread/goal/updated`, including objective, status, token budget, tokens used, and elapsed time. `thread/goal/cleared` keeps `event.goal` as `None` and preserves source thread/turn identity.

This is intentionally not a portable workflow primitive. It is Codex app-server native session state made observable through Yoke's event seam. Claude SDK goals remain compiled context or `/goal` loop initiation unless Claude exposes equivalent readable stream state through the SDK.

Touched files:

- `src/yoke/models.py`
- `src/yoke/providers/codex_app/events.py`
- `tests/test_codex_app_events.py`

Verification:

- `PYTHONPATH=src uv run pytest tests/test_codex_app_events.py tests/test_goals.py tests/test_sessions.py` -> 34 passed
- `uv run ruff check src/yoke/models.py src/yoke/providers/codex_app/events.py tests/test_codex_app_events.py` -> all checks passed

Follow-up in the same slice: Codex app-server `start()` and `fork()` now set `Session.provider_session_id` to the returned thread id immediately. This keeps goal-loop handles, forks, and app integrations from waiting for a later turn event before they can refer to the provider thread.
