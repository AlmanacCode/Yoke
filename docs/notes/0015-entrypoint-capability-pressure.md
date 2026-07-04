# Entrypoint capability pressure

Yoke must model provider entrypoints, not only providers.

The hard abstraction is not `claude` versus `codex`. The hard abstraction is:

- Claude CLI
- Claude Python SDK
- Claude TypeScript SDK, if it exposes different controls
- Codex CLI
- Codex app-server
- future Codex SDK surfaces

Each entrypoint can expose a different capability envelope. A feature should be attached to the narrowest true surface:

| Feature | Capability question |
| --- | --- |
| Streaming | Does this entrypoint emit structured events or only final text? |
| Sessions | Does it resume provider-owned state, or does Yoke rebuild state? |
| Goals | Does it support mutable provider goals, or only prompt-compiled intent? |
| Subagents | Does it support native subagents, or only instruction compilation? |
| Skills | Does it load native skill folders, or does Yoke inline skill text? |
| Tools | Does it expose tool call lifecycle events, or only terminal output? |
| Permissions | Does it accept sandbox/approval policy, or is this CLI-only process policy? |
| Workflows | Does the provider run the workflow, or does Yoke orchestrate multiple turns? |

The default rule is: preserve native behavior when the surface supports it; compile down only when the surface does not.

This keeps Yoke honest. `Harness(provider="codex")` should choose a sane default, but `Harness(provider="codex", surface="app_server")` must be allowed to expose more than `Harness(provider="codex", surface="cli")`.

The Codex app-server is currently the richest known Codex surface. It has structured streaming, thread state, native goal methods, and app-server-level skill controls. The Codex CLI is simpler and useful for portability, but it should not define the ceiling of the Codex model.

Claude should get the same treatment. The Python SDK and CLI must be researched separately before we claim support for workflows, subagents, goals, permissions, or streaming. If Claude exposes a feature in one surface but not another, Yoke should record that as a capability difference rather than hiding it behind a leaky boolean.

Design implication: provider adapters should expose a `Capabilities` object that can say:

- supported
- emulated by Yoke
- compiled into prompt
- unsupported
- unknown until runtime

This is especially important for goals. A native mutable goal changes the provider run contract. A prompt-compiled goal is just instructions. They should share the user-facing `Goal` model, but not pretend to be the same execution mechanism.

