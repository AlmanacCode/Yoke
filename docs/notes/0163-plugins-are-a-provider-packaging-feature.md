# Plugins are a provider packaging feature

Date: 2026-07-04

Yoke now tracks `Feature.PLUGINS` separately from `Feature.SKILLS`.

Skills are reusable capability content. Plugins are provider packaging and
loading mechanisms that may include skills, agents, hooks, MCP servers,
commands, app integrations, or provider config.

The distinction is surface-specific:

- Claude Python SDK can load local plugin roots, and Yoke already uses that for
  folder skills.
- Codex CLI/app surfaces document plugin support. Yoke can bundle provider files,
  but it does not install Codex plugins directly yet.
- Codex Python SDK is not marked plugin-capable because current Yoke evidence
  does not show a public plugin install/import operation through that adapter.

This prevents a common false simplification: "skills support" does not imply
"plugin management support." A provider can support native skills without Yoke
owning plugin installation, and a plugin can carry more than skills.

Follow-up: `Artifact` now carries typed `component` and `feature` metadata.
Current bundles emit provider-native file components such as `agent`, `skill`,
`workflow`, and `config`. They do not emit a `plugin` component yet. A future
plugin writer should add explicit plugin artifacts rather than hiding plugin
installation behind ordinary skill bundles.
