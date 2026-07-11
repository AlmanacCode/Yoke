# 0046 - Bundles are explicit provider artifacts

Yoke needs a public boundary between a portable `Agent` definition and
provider-native filesystem configuration. The right noun is `Bundle`: a set of
`Artifact` files compiled for one provider surface.

This follows two current provider facts.

Codex:

- Skills are directories with `SKILL.md` files. Repository-scoped skills live
  under `.agents/skills` and must include `name` and `description`.
- Custom agents are TOML files under `.codex/agents` or `~/.codex/agents`. Each
  file defines one agent with `name`, `description`, and
  `developer_instructions`.

Claude:

- Skills are filesystem artifacts under `.claude/skills/<name>/SKILL.md`, user
  skills, enterprise skills, or plugin skills.
- Project subagents are markdown files under `.claude/agents/`; the file has
  YAML frontmatter plus a markdown body that becomes the subagent system prompt.
- Claude plugins can package skills, agents, hooks, and MCP servers, but Yoke is
  not generating plugin roots yet.

Yoke now exposes:

```python
bundle = agent.bundle(provider="codex", surface="codex_cli")
bundle.write(Path.cwd())
```

`bundle.write()` is explicit and refuses to overwrite existing files unless
`overwrite=True`. Running a Yoke harness still does not silently create
`.codex/`, `.agents/`, or `.claude/` files.

The compiler currently generates:

- Codex subagents: `.codex/agents/*.toml`
- Codex inline skills: `.agents/skills/<name>/SKILL.md`
- Claude subagents: `.claude/agents/*.md`
- Claude inline skills: `.claude/skills/<name>/SKILL.md`

Path-backed skills are not copied. They already point at existing provider
artifacts.

Sources checked on 2026-07-04:

- current Codex manual from `fetch-codex-manual.mjs`
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/agent-sdk/plugins
