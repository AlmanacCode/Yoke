# Bundle artifacts carry lowering text

Date: 2026-07-04

Provider-native bundle artifacts now carry `lowering`.

Capability reports explain how a feature behaves on a surface. Bundles are more concrete: they are the actual files Yoke can write into a repo. The `Artifact` model now includes `lowering` so a caller inspecting `agent.bundle(...)` can explain each generated file without knowing the provider's conventions.

Examples:

- `.codex/agents/reviewer.toml` is a Yoke subagent compiled to Codex custom-agent TOML.
- `.agents/skills/docs-research/SKILL.md` is a Yoke inline skill compiled to a Codex filesystem skill.
- `.claude/agents/researcher.md` is a Yoke subagent compiled to Claude custom subagent markdown.
- `.claude/skills/release/SKILL.md` is a Yoke inline skill compiled to a Claude filesystem skill.

Design implication: artifact metadata should teach the lowering path at the file level. `FeatureReport.lowering` explains surface behavior; `Artifact.lowering` explains a concrete generated file. This keeps Yoke folder source, provider-native bundles, and runtime behavior separate but connected.

Docs checked during the slice:

- Codex subagents: https://developers.openai.com/codex/subagents
- Claude Agent SDK subagents: https://code.claude.com/docs/en/agent-sdk/subagents
- Claude Agent SDK skills: https://code.claude.com/docs/en/agent-sdk/skills
