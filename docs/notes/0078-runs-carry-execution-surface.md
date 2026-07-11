# Runs carry execution surface

Yoke runtime results should carry the concrete surface that executed the work. `Session` already records `surface`; `Run` now does too.

This is not just diagnostics. Surface is part of the semantic contract because Codex CLI, Codex Python SDK, Codex app-server, Claude Python SDK, and conceptual TypeScript surfaces expose different behavior. A caller inspecting a result should be able to tell which contract produced it.

Built-in adapters populate `Run.surface`. Third-party adapters may omit it during migration because the field is optional, but Yoke-owned results should be self-describing.

This also helps CodeAlmanac integration later: lifecycle jobs can store `provider` and `surface` evidence without inferring it from logs or session ids.
