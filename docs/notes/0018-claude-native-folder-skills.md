# Claude native folder skills

Claude's Agent SDK can load local plugins with:

```python
ClaudeAgentOptions(
    plugins=[{"type": "local", "path": "/path/to/plugin-root"}],
)
```

The official plugin SDK docs say the path must point at the plugin root: the parent of `skills/`, `agents/`, `hooks/`, `commands/`, or `.claude-plugin/`. The plugin reference says skills live at:

```text
skills/<skill-name>/SKILL.md
```

That matches a Yoke folder agent:

```text
agent/
├── agent.yaml
├── instructions.md
└── skills/
    └── source-grounding/
        └── SKILL.md
```

Yoke now preserves `Agent.root` when loading an agent from a folder. The Claude adapter uses that root as a local plugin when it contains `skills/`.

This means packaged Yoke skills are native for both rich surfaces:

- Claude Python SDK: local plugin root.
- Codex app-server: `skills/extraRoots/set`.

Inline skills still compile into prompt text because they have no filesystem root for Claude or Codex to scan.

Yoke deliberately does not generate a `.claude-plugin/plugin.json` yet. Claude's docs say the manifest is optional when components use default locations. Avoiding generated files keeps the folder itself as the source of truth.

The important behavior change is in the Claude options:

- If native plugin paths exist, Yoke passes `plugins=[...]`.
- It sets `skills="all"` so namespaced plugin skills are available without Yoke guessing the plugin namespace.
- It skips prompt-compiling packaged plugin skills to avoid double injection.

The tradeoff is that Claude may see all discovered skills for that plugin root. That is acceptable for now because the plugin root is the Yoke agent folder, not the user's whole global Claude config.

Sources checked:

- <https://code.claude.com/docs/en/agent-sdk/plugins>
- <https://code.claude.com/docs/en/plugins>
- <https://code.claude.com/docs/en/plugins-reference>

