# Entrypoints are feature boundaries

Yoke must treat provider entrypoints as separate capability boundaries.

The useful question is not "does Codex support streaming?" or "does Claude
support workflows?" The useful question is "which Codex or Claude entrypoint
supports this feature, and at what exposure level?"

Codex currently has at least three materially different entrypoints:

- `codex:app`: the app-server surface. This is the richest embedding surface
  for Yoke. It exposes JSON-RPC sessions, streamed events, provider session
  state, approval and user-input requests, collaboration events, goal state,
  and app-level lifecycle controls.
- `codex:sdk`: the Python SDK surface. It is useful for Python callers, but it
  is not automatically equal to the app-server feature set even when it talks
  to app-server internally.
- `codex:cli`: the local CLI surface. It is useful for simple filesystem
  agent runs, but it should not define Yoke's Codex abstraction.

Claude has the same shape. Claude Agent SDK features, Claude CLI behavior,
Claude skill loading, and Claude TypeScript workflow support should not be
collapsed into a single provider-wide claim.

Design rule: every Yoke capability claim must identify `provider:surface`.
Portable Yoke APIs may hide that choice for simple calls, but status reports,
feature lowering, live smoke evidence, adapter support, and docs should keep
the entrypoint visible.

This matters most for features that change execution semantics:

- streaming
- approval and user-input requests
- subagents and collaboration events
- workflows
- goals and goal loops
- session resume, fork, interrupt, compact, rename, and readback
- skill and plugin loading

Implementation consequence: prefer adding or refining a surface-specific
adapter contract over adding a provider-wide boolean. If a feature is richer on
`codex:app` than `codex:sdk`, Yoke should say that directly instead of
pretending the provider supports one uniform behavior.
