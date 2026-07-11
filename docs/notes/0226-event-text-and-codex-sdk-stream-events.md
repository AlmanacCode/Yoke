# Event text alias and Codex SDK stream events

2026-07-04

Yoke events now expose `event.text` as a readable alias for `event.message`.

The stored field remains `message`, because tool events, request events, usage events, and provider status events all need a generic display string. The alias makes event streaming examples read naturally without changing serialized event shape.

Codex Python SDK fallback stream events now use `EventKind.STREAM_EVENT` instead of leaking arbitrary provider method strings into `event.kind`. The provider method is preserved in `event.message`, and the original SDK event remains in `event.raw`.

Codex app-server unknown notifications are also preserved as `EventKind.STREAM_EVENT` instead of being dropped. Known app-server notifications still map to specific Yoke kinds such as `text_delta`, `tool_use`, `tool_result`, `context_usage`, `goal_updated`, `approval_request`, and `request_resolved`.

Codex app-server `account/rateLimits/updated` notifications now map to `EventKind.RATE_LIMIT`. The Codex payload is a sparse account-level rate-limit snapshot, not token usage for a specific turn, so Yoke preserves it in `event.raw` instead of forcing it into `Usage`.

Codex app-server `item/autoApprovalReview/started` and `item/autoApprovalReview/completed` notifications now map to `EventKind.TOOL_SUMMARY`. The Codex app-server README marks this review payload as unstable and temporary, so Yoke does not add a stable public review model. It exposes target item id, action/review payload, action-derived `ToolKind`, error status for denied/aborted reviews, and the raw provider payload.

Codex app-server `item/fileChange/patchUpdated` notifications now map to `EventKind.TOOL_SUMMARY` with `ToolKind.EDIT`. This event represents progress/diff state for an in-flight file change, not the final edit result, so the final `item/completed` event remains the authoritative tool result.

This keeps the event contract provider-neutral while still preserving provider-native detail for embedders that need it.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_events.py tests/test_codex_python_sdk.py tests/test_codex_app_events.py`
- `PYTHONPATH=src uv run ruff check src/yoke/models.py src/yoke/providers/codex_sdk.py src/yoke/providers/codex_app/events.py tests/test_events.py tests/test_codex_python_sdk.py tests/test_codex_app_events.py`
