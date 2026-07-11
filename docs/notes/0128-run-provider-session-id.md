# Run provider session id

2026-07-04

Yoke now exposes `Run.provider_session_id` as a convenience property.

Provider-native session identity can arrive in two places:

- `Run.session.provider_session_id`, when the adapter returns or updates a session handle.
- `Event.provider_session_id`, when the provider announces a session or thread id through the stream.

Embedding apps should not have to know which surface produced which shape just to record a transcript/session reference. The property prefers `Run.session.provider_session_id` and then falls back to the latest event with `provider_session_id`.

This is intentionally generic. CodeAlmanac can map the property into `HarnessTranscriptRef.session_id`, while other embedders can use it for logs, dashboards, or resume handles.
