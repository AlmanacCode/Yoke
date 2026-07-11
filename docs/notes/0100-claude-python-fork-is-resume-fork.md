# Claude Python fork is resume-fork

Yoke now supports `Session.fork()` on `claude_python_sdk` only after it knows the provider-persisted Claude session id.

The implementation starts a second `ClaudeSDKClient` with `resume=<provider_session_id>` and `fork_session=True`. The fork receives a new Yoke-local `Session.id`; its new provider session id is learned later from provider events after the forked session runs.

Yoke rejects `ForkOptions.last_turn_id` and `ForkOptions.exclude_turns` for Claude Python live fork. The Claude SDK's live resume-fork surface does not expose the same partial-fork controls that Codex app-server exposes. Claude also has transcript-level `fork_session()` helpers that can fork up to a message id, but those are offline session-file/store mutations, not the same as forking a connected `ClaudeSDKClient`.

Implication: `Feature.FORK` is native for `claude_python_sdk`, with scoped semantics: full persisted-session fork, provider id required, new provider id learned from events.
