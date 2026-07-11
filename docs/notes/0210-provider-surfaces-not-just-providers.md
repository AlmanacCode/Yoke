# Provider surfaces, not just providers

Yoke must track support at the provider-surface level, not just at the provider level. A statement like "Codex supports streaming" or "Claude supports workflows" is incomplete unless it names the API surface that exposes the feature.

Current design constraint:

- `Provider` answers who runs the agent: `codex`, `claude`.
- `Surface` answers how Yoke talks to it: SDK, CLI, app server, direct subprocess, future hosted/server surfaces.
- `Feature` answers what Yoke can rely on for this run: streaming events, request callbacks, request events, goals, subagents, native workflows, folder loading, resume, transcript access, tool approval semantics.
- Planning must resolve against `(provider, surface, options)`, not `(provider)`.

Why this matters:

- Codex app server appears to be the richest Codex surface for evented control, request handling, streaming-style updates, and app-native semantics.
- Codex CLI/subprocess style may be better for simple one-shot execution but can expose fewer structured controls.
- Claude Agent SDK exposes rich programmable options, including subagents, permission callbacks, and TypeScript workflow tooling.
- Claude CLI behavior may not expose every SDK-only affordance in a way Yoke can compose safely.
- Some features are native on one surface and emulated on another. Yoke should say that explicitly through capability planning rather than hiding it behind one provider name.

Implementation pressure:

- Keep `Feature` small and concrete.
- Keep `Surface` first-class in `Harness` and `RunOptions`.
- Add tests whenever a provider option implies a feature, especially for app-server request handling, Claude permission callbacks, workflow support, and goal support.
- Prefer graceful degradation with an explicit plan over pretending feature parity exists.
- Preserve provider-specific escape hatches, but keep common Yoke objects serializable when they are folder-native.

This is especially important for goals. A Yoke `Goal` may map to a native Codex app-server/app concept, a Codex SDK/CLI option, a Claude SDK prompt contract, or a Yoke loop. Those are not the same operational unit, so the capability planner must say which one is active.
