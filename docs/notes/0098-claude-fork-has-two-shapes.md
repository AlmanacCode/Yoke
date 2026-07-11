# Claude fork has two shapes

Claude should also stay surface-specific in Yoke.

The official Claude CLI exposes `--fork-session` when resuming or continuing a session. That is a native CLI capability, but Yoke does not currently have a Claude CLI adapter.

The Claude Python Agent SDK exposes two related fork paths. It exports `fork_session()` and `fork_session_via_store()` helpers that copy persisted session transcripts with remapped UUIDs. It also has `ClaudeAgentOptions(fork_session=True)`, documented as a resume option that forks to a new session ID rather than continuing the previous session.

Yoke's current runnable Claude adapter uses `ClaudeSDKClient` for live sessions, but `Claude.start()` currently creates a Yoke UUID before Claude has produced a persisted provider session ID. The adapter maps provider session IDs into events, but the `Session` object itself is still keyed by the Yoke-generated id. Because of that, claiming `Session.fork()` works for live Claude sessions would be dishonest.

Implication: keep `claude_python_sdk` fork support as `unknown` until Yoke stores provider session identity explicitly or starts Claude sessions from a known persisted `resume` id. Mark `claude_cli` fork as native conceptually because the CLI exposes the flag, while keeping it non-runnable until Yoke has a CLI adapter.
