"""OpenCode filesystem agent (custom subagent) rendering.

OpenCode discovers subagents from markdown files with YAML frontmatter —
confirmed at https://opencode.ai/docs/agents/: a global
`~/.config/opencode/agents/*.md` or per-project `.opencode/agents/*.md`
directory, filename becomes the agent id, `mode: subagent` marks it
invokable via `@mention` or auto-delegation rather than as a primary agent.
Scoped to direct Yoke subagents only (mirrors `codex_agent_files`'s scope) —
OpenCode's docs describe no nested subagent-of-subagent invocation model to
compile against.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yoke.models import Access, Agent
from yoke.providers.codex_agents import description_for, instructions_for, slug


@dataclass(slots=True)
class OpencodeAgentFile:
    """One `.opencode/agents/*.md` file Yoke can materialize explicitly."""

    name: str
    path: Path
    text: str


def opencode_agent_files(
    agent: Agent,
    *,
    directory: str | Path = ".opencode/agents",
) -> tuple[OpencodeAgentFile, ...]:
    """Compile direct Yoke subagents to OpenCode custom-agent markdown files."""

    root = Path(directory)
    return tuple(
        OpencodeAgentFile(
            name=name,
            path=root / f"{slug(name)}.md",
            text=opencode_agent_markdown(name, subagent),
        )
        for name, subagent in agent.subagents.items()
    )


def opencode_agent_markdown(name: str, agent: Agent) -> str:
    """Render one OpenCode custom-agent markdown document."""

    lines = [
        "---",
        f"description: {yaml_string(description_for(name, agent))}",
        "mode: subagent",
    ]
    if agent.model:
        lines.append(f"model: {yaml_string(agent.model)}")
    permission = _agent_permission_config(agent)
    if permission:
        lines.append("permission:")
        for tool, action in permission.items():
            lines.append(f"  {tool}: {action}")
    lines.extend(["---", "", instructions_for(agent)])
    return "\n".join(lines) + "\n"


def _agent_permission_config(agent: Agent) -> dict[str, str]:
    """Translate this subagent's own access/network posture into OpenCode's
    per-agent `permission:` frontmatter key (confirmed live: a `bash: deny`
    entry here genuinely blocks the tool, independent of whatever the
    parent session's own ruleset allows).

    Mirrors `codex_agent_toml`'s `sandbox_mode(agent.permissions)` — the
    same subagent-level `access` field already gates Codex's sandbox, so a
    subagent left at the default `Permissions()` (access=READ) already gets
    Codex's "read-only" treatment; without this, the identical subagent
    compiled to OpenCode had no restriction at all, inheriting whatever the
    parent session/process happened to allow. Approval is intentionally not
    translated here, matching Codex's own subagent compiler, since there is
    no live per-request approval signal at subagent granularity.
    """

    permissions = agent.permissions
    denies: dict[str, str] = {}
    if permissions.access not in (Access.WRITE, Access.FULL):
        for tool in ("write", "edit", "apply_patch"):
            denies[tool] = "deny"
    if permissions.access is not Access.FULL:
        denies["bash"] = "deny"
    if not permissions.network:
        for tool in ("webfetch", "websearch"):
            denies[tool] = "deny"
    return denies


def yaml_string(value: str) -> str:
    # A JSON string literal is also a valid YAML double-quoted scalar, so
    # this avoids hand-rolling YAML quoting/escaping rules — same trick
    # codex_agents.py's toml_string uses for TOML basic strings.
    return json.dumps(value)
