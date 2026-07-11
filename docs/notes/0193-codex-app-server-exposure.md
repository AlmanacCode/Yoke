# 0193 - Codex app-server exposure

Codex app-server options now expose their surface shape directly.

`CodexOptions.app_server_exposure()` returns `CodexAppServerExposure` with three
sets of fields:

- `stable`: serializable initialize capability fields that can round-trip
  through folder/source configuration.
- `experimental`: protocol fields gated by `experimentalApi`.
- `runtime`: live Python objects, such as `request_handler`, that must stay in
  SDK code.

This keeps app integrations from guessing whether a Codex option is a durable
protocol field or an embedding concern. It also mirrors the Claude permission
callback split from note 0192: folder source is durable, provider protocol
fields are explicit, and live callbacks are visible through runtime reports
without being serialized.

References:

- <https://developers.openai.com/codex/app-server>
- <https://developers.openai.com/codex/cli/reference>
