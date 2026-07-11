# Feature parity is entrypoint-specific

Date: 2026-07-04

Yoke must not model Claude or Codex as single flat providers. The important compatibility unit is provider + entrypoint + channel + runtime.

Codex is the sharp example. The app server appears to expose the richest surface, including streaming/session behavior and app-native controls. The CLI, SDK, app server, and desktop app can differ in available features, option names, event shapes, and lifecycle semantics.

Claude has the same class of problem. Claude Code CLI behavior, SDK behavior, filesystem-discovered agents/skills, and workflow/script affordances are related but not identical. Yoke should record which entrypoint supports a feature instead of assuming all Claude surfaces do.

Design implication:

- `provider="codex"` is not enough to decide whether goals, subagents, workflows, streaming, interrupts, skills, plugins, or session mutation are available.
- Capability checks should be driven by a `Status` or `Surface` record that names the entrypoint and the evidence behind each feature.
- Lowering should be explicit. If a Yoke object can be represented natively on one entrypoint but only emulated on another, that needs to be visible in the artifact/result metadata.
- CodeAlmanac should ask Yoke what this exact harness surface supports. CodeAlmanac should not hard-code broad provider assumptions.

Research checklist for future slices:

- Codex app server feature map.
- Codex CLI feature map.
- Codex SDK feature map.
- Codex desktop/app feature map if accessible.
- Claude Code CLI feature map.
- Claude Agent SDK feature map.
- Claude filesystem-discovered agents, skills, plugins, hooks, and workflow/script behavior.

This note should shape the API: Yoke should feel like `Harness(provider=..., surface=...)`, not `ProviderHasFeature(provider)`.
