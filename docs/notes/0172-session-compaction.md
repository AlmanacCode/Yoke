# 0172 - Session compaction is surface-specific

Yoke exposes `Session.compact()` as a session-control operation, not as a generic provider operation.

Codex app-server lowers `Session.compact()` to `thread/compact/start`. That endpoint starts compaction for an existing thread and returns immediately, so Yoke treats the call as a control request rather than a new run result.

Claude checkpointing is not the same operation. Claude file checkpoints can rewind filesystem changes, but they do not provide a portable conversation-history compaction API that Yoke can expose as `Session.compact()`.

The capability matrix must stay surface-specific. Codex app-server can be native while Codex CLI, Codex SDK, Claude CLI, and Claude SDK surfaces remain unsupported or unknown until their exact control APIs are wired and tested.
