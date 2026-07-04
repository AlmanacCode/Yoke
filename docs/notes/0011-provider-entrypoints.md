# Provider entrypoints are part of the contract

Yoke must not model provider support at the provider name level alone. Codex and Claude expose different feature sets through different entrypoints, and those differences are architectural, not implementation noise.

For Codex, the app server appears to be the richest surface. It owns thread/session state, mutable goals, streaming events, app-facing control-plane semantics, and internal run coordination. The CLI is useful for one-shot and resumable execution, but it cannot honestly expose every app-server feature. Any Codex support matrix must distinguish at least `codex_cli`, `codex_ts_sdk`, and `codex_app_server`.

For Claude, the Python Agent SDK and CLI/documented agent surfaces need the same treatment. Claude subagents, tools, MCP servers, permission options, client sessions, and workflow-like patterns do not all live at the same abstraction layer. Yoke should expose what each surface can really do, then compile portable Yoke concepts only when the behavior remains honest.

Design pressure:

- `Harness(provider="codex")` is convenient, but serious callers should be able to select or inspect the surface.
- Capabilities should answer "can this exact surface do this natively?", "can Yoke compile/emulate it?", and "is it unsupported?"
- Streaming, goals, sessions, subagents, workflows, tools, permissions, and skills all need per-surface capability entries.
- Yoke should avoid a weak common denominator; the public API should stay simple while provider adapters preserve richer native behavior.
- CodeAlmanac integration must call Yoke at the harness/provider seam without letting Yoke own CodeAlmanac jobs, lifecycle state, or product operations.

This is a tricky project because "Codex supports goals" is not precise enough. The better question is: "Which Codex surface supports mutable goals, with what lifecycle, event stream, and cancellation semantics?"
