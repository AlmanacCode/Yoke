# 0194 - Status exposure report

`Status.exposure` now reports where provider-surface configuration naturally
lives.

The report has a small shape:

- `mode`: `cli`, `sdk`, `protocol`, or `unknown`.
- `protocol`: a readable protocol label such as `codex_app_server_json_rpc`.
- `stable`: whether the surface has durable serializable configuration.
- `experimental`: the surface's `Feature.EXPERIMENTAL_API` support.
- `runtime_options`: whether live SDK objects are expected on that surface.

This complements `CodexOptions.app_server_exposure()`. Option exposure answers
"what did this concrete option object configure?" Status exposure answers "what
kind of surface is this before I construct options?"

The distinction matters because Codex app-server, Codex SDK, Codex CLI, and
Claude SDK expose different integration levels. Yoke should explain those
levels directly instead of making users infer them from provider names.

References:

- <https://developers.openai.com/codex/app-server>
- <https://developers.openai.com/codex/cli/reference>
- <https://code.claude.com/docs/en/agent-sdk/overview>
