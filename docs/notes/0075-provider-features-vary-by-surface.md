# Provider features vary by surface

Yoke must treat provider features as surface-specific, not provider-wide. Codex is the clearest example: the CLI, Python SDK, TypeScript SDK, and app-server expose different contracts, and the app-server appears to carry the richest stateful surface for threads, turns, streaming, and app-level controls.

Claude has the same shape in a different form. The CLI, Python SDK, TypeScript SDK, and managed-agent/workflow surfaces do not all expose the same knobs, even when they target the same underlying Claude agent runtime.

Design consequence: every feature decision should ask `provider + surface`, not just `provider`. A Yoke `Harness(provider="codex")` may choose a default, but planning, diagnostics, and execution must preserve the resolved surface so unsupported features fail with a precise explanation.

Research consequence: when adding support for goals, streaming, workflows, subagents, skills, hooks, structured output, login, or collaboration modes, check each official surface separately. Do not infer support from one Codex or Claude entry point to another.

Current bias: prefer app-server-backed Codex support for the richest Codex behavior, while keeping CLI and SDK surfaces available for simpler or more portable usage.
