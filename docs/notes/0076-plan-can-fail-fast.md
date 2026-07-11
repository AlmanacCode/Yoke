# Plan can fail fast

Yoke `Plan` is a non-executing surface-resolution object. Callers can inspect it when they want diagnostics, or call `raise_for_status()` when they want the same resolution to become an execution guard.

This keeps planning and enforcement on the same object. A UI can show `plan.candidates`; a service path can call `plan.raise_for_status()` before dispatching work. Both paths use the same provider/surface feature evidence.

The failure names the resolved `provider:surface` and the missing features. This matters because unsupported behavior is usually surface-specific: `codex:codex_typescript_sdk` may fail a requirement that `codex:codex_app_server` can satisfy.
