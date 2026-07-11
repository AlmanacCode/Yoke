# Skill status tracks native bundles versus compiled prompt context

Date: 2026-07-04

Yoke now exposes `status.skills`.

The report has:

- `skills`: support for provider skill bundles.
- `hooks`: support for provider hooks.
- `mcp`: support for provider MCP configuration.
- `mode`: `provider_native`, `compiled`, `unknown`, or `unsupported`.

Skills differ from ordinary instructions because they are progressively disclosed filesystem bundles. A skill folder contains `SKILL.md` plus optional scripts, references, and assets. Providers usually load a short skill summary first, then load the full skill only when the model chooses it.

Codex documents skills as directories with a required `SKILL.md`. Codex discovers repository, user, admin, and system skills; it can invoke skills explicitly with `$skill` or implicitly by matching the skill description. Codex app-server exposes `skills/list` and `skills/extraRoots/set`, so Yoke can keep path-backed skill bundles native on app-server instead of flattening everything into the prompt.

Claude Agent SDK documents skills as filesystem artifacts under `.claude/skills/`, loaded by `setting_sources` / `settingSources` and filtered with the SDK `skills` option. Claude SDK does not provide a programmatic API for registering arbitrary inline skills as native skill bundles, so Yoke inline text skills remain prompt context while path-backed skills can stay native.

Current status semantics:

- `provider_native`: the selected surface can discover or load filesystem skill bundles.
- `compiled`: Yoke turns the skill into instructions for that surface.
- `unknown`: Yoke has not verified the surface.
- `unsupported`: the selected surface should reject skill use.

Sources checked:

- https://developers.openai.com/codex/skills
- https://code.claude.com/docs/en/agent-sdk/skills
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
