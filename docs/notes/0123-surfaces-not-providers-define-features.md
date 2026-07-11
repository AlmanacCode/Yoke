# Surfaces, not only providers, define Yoke features

2026-07-04

Yoke must model provider surfaces explicitly because `provider="codex"` or `provider="claude"` is not enough to predict feature support.

Codex currently exposes different capabilities through the CLI, the Python SDK, and the app server. The app server appears to be the richest surface because it exposes initialization capabilities, streaming JSON-RPC events, and collaboration notifications that are not necessarily available through the simpler CLI or Python SDK path. The Python SDK wraps and controls the local Codex app-server runtime, so it should not be treated as equivalent to invoking `codex exec`.

Claude similarly has a Python Agent SDK surface with native `AgentDefinition` subagents, sessions, hooks, skills, and structured options. Those SDK-native features should not be flattened into a generic provider label, because the CLI or future surfaces may expose a different subset or different control model.

The design rule is: feature planning asks for a provider plus surface, then maps the requested Yoke feature to the strongest compatible implementation on that surface. `surface="auto"` may choose a richer surface when the requested features require it, but Yoke should make that decision visible through `Harness.report()` and `Harness.status()`.

This matters for goals, workflows, subagents, streaming, resume/session behavior, MCP, and provider-specific initialization options. A portable Yoke API can exist, but it must be honest about whether a feature is native, compiled into instructions, emulated by Yoke, or unsupported on the selected surface.
