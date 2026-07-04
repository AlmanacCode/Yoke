# Codex app-server native skills

Codex app-server has a native skill surface. The useful methods are:

- `skills/extraRoots/set`
- `skills/list`
- `skills/config/write`

The TypeScript schema for `skills/extraRoots/set` is small:

```ts
export type SkillsExtraRootsSetParams = { extraRoots: Array<AbsolutePathBuf> };
```

The docs show `skills/list` scanning roots that contain skill folders. A returned skill path looks like:

```text
/Users/me/.codex/skills/skill-creator/SKILL.md
```

That means a Yoke packaged skill at:

```text
agent/skills/source-grounding/SKILL.md
```

should be passed to app-server as the root:

```text
agent/skills
```

Yoke now does that for the Codex app-server adapter. Packaged skills are native on that surface. Inline skills created with `Skill.from_text(...)` still compile into developer instructions because there is no filesystem root for app-server to scan.

This keeps the entrypoint distinction intact:

- Codex app-server: native roots for packaged skills, prompt compilation for inline skills.
- Codex CLI: prompt compilation until a real CLI skill-loading surface is proven.
- Claude Python SDK: existing adapter behavior until we separately prove native local skill-folder wiring.

The important rule is not "skills are native" or "skills are prompt text." The rule is: the same Yoke `Skill` model compiles differently depending on the entrypoint's real capability envelope.

