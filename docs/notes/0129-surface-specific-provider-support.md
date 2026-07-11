# Surface-specific provider support is a core Yoke constraint

Date: 2026-07-04

Yoke must model provider surfaces, not only providers.

The same vendor exposes different features through different entry points. Codex has at least CLI, Python SDK, and app-server surfaces. Claude has CLI and Agent SDK surfaces, plus TypeScript/Python SDK differences. Yoke cannot safely answer "does Codex support X?" or "does Claude support Y?" without asking "through which surface?"

Codex app-server appears to be the richest Codex integration surface for Yoke-style embedding. It exposes streamed events, app/session lifecycle, initialization capabilities, notification/form elicitation knobs, approval semantics, and collaboration-style event payloads. Codex CLI is simpler and useful for local one-shot execution, but it should not define the whole Codex capability model. Codex Python SDK currently wraps/control-surfaces over local app-server behavior and has its own packaging/auth constraints.

Claude Agent SDK exposes sessions, streaming input, hooks, custom tools, subagents, skills, and client-side interruption behavior. Claude workflow support is surface-specific too: TypeScript documents a native Workflow tool shape, while Python should be treated as portable/emulated workflow support unless current docs or runtime evidence prove otherwise.

Design implication: Yoke capability checks should be surface-aware and evidence-backed. `provider="codex"` with `surface="auto"` should choose the smallest surface that satisfies requested features, but explicit aliases such as `codex:app`, `codex:sdk`, `claude:sdk`, and future `claude:ts-sdk` should preserve the user's intent.

This affects goals, workflows, subagents, skills, streaming, approvals, interrupts, session resume, tool display, usage accounting, and embeddability into CodeAlmanac. The framework should avoid flattening those differences into a false lowest-common-denominator API. It should instead expose a clean portable model plus provider/surface reports that explain what is native, emulated, unsupported, or unknown.

Next pressure test: keep comparing current official docs and live smoke behavior for each surface before claiming support. The README and capability reports should make unsupported or emulated behavior obvious rather than surprising at runtime.
