# 0047 - Login is explicit, readiness stays non-invasive

Yoke now separates readiness from login.

`Harness.check()` answers whether a provider surface appears usable enough to
try a run. It must not start browser flows, mutate credential stores, or prompt
the user.

`Harness.login()` starts provider-native auth only when the selected surface has
a programmatic flow. The first implementation is Codex Python SDK because the
`openai-codex` package documents:

- `login_chatgpt()` for browser ChatGPT login
- `login_chatgpt_device_code()` for device-code login
- `login_api_key(api_key)` for API-key login

`Login.wait()` waits for browser or device-code handles and returns an updated
`Login` value. API-key login completes immediately.

Other surfaces remain external for now:

- Codex CLI users run `codex login`.
- Codex app-server uses the existing Codex auth cache.
- Claude SDK users set `ANTHROPIC_API_KEY` or authenticate through Claude Code.

This keeps Yoke from pretending every provider has the same auth model, while
still letting embedded applications offer normal OAuth/device-code/API-key
flows when the underlying SDK exposes them.

Sources checked on 2026-07-04:

- current Codex manual from `fetch-codex-manual.mjs`
- https://developers.openai.com/codex/sdk
