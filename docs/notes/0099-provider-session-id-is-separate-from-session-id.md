# Provider session id is separate from Yoke session id

Yoke sessions need two identities.

`Session.id` is the Yoke live-session key. Adapters use it to find live local process state such as a `ClaudeSDKClient`, Codex app-server process, or SDK thread wrapper.

`Session.provider_session_id` is the provider-persisted conversation identity when a provider exposes one. Claude often reveals this through system/result events after the process starts. Codex app-server and SDK surfaces often use the provider thread id as the live key already, but Yoke should not assume every provider behaves that way.

This distinction matters for Claude fork. Claude Python SDK exposes `fork_session()` helpers and `ClaudeAgentOptions(fork_session=True)` for resumed sessions, but those operate on persisted Claude session ids. Yoke's previous Claude adapter created a local UUID at `start()`, which was not necessarily the Claude persisted id. Exposing `Session.fork()` against that local UUID would have been dishonest.

Implication: provider-native identity should be captured from events and carried on `Session.provider_session_id`. Future Claude fork support should use this field, not `Session.id`, when resuming or forking persisted Claude conversations.
