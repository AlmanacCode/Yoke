"""Ephemeral provider-native files derived from a canonical Yoke agent."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from yoke.errors import YokeError
from yoke.models import Agent, Provider, Skill
from yoke.providers.codex_agents import (
    codex_agent_name,
    codex_agent_toml,
    description_for,
    instructions_for,
    option_mapping,
    slug,
)
from yoke.providers.codex_app.prompts import native_subagents
from yoke.providers.codex_app.skills import native_skill_root
from yoke.providers.native_skills import (
    direct_inline_skills,
    inline_skills,
    native_skill_text,
    skill_directory_name,
)


@dataclass(slots=True)
class RuntimeDeployment:
    """One isolated provider projection whose owner controls its lifetime."""

    provider: Provider
    root: Path
    codex_agents: dict[str, dict[str, str]]
    codex_role_names: dict[str, str]
    codex_skill_roots: tuple[Path, ...] = ()
    codex_parent_skill_settings: tuple[tuple[Path, bool], ...] = ()
    generated_skill_root: Path | None = None
    claude_plugin_root: Path | None = None
    claude_plugin_name: str | None = None
    opencode_config_dir: Path | None = None
    opencode_config_content: str | None = None

    def cleanup(self) -> None:
        """Remove only this deployment, never authored files."""

        shutil.rmtree(self.root, ignore_errors=True)


def deploy_runtime(
    agent: Agent,
    provider: Provider | str,
    parent: Path | None,
) -> RuntimeDeployment:
    """Compile runtime-only native files under a unique temporary directory."""

    provider = Provider(provider)
    parent = runtime_parent(parent)
    parent.mkdir(parents=True, exist_ok=True)
    reclaim_stale_deployments(parent)
    root = Path(
        tempfile.mkdtemp(
            prefix=f"yoke-{provider.value}-{os.getpid()}-",
            dir=parent,
        )
    )
    deployment = RuntimeDeployment(
        provider=provider,
        root=root,
        codex_agents={},
        codex_role_names={},
    )
    try:
        if provider is Provider.CODEX:
            _write_codex(agent, deployment)
        elif provider is Provider.OPENCODE:
            _write_opencode(agent, deployment)
        else:
            _write_claude(agent, deployment)
        return deployment
    except Exception:
        deployment.cleanup()
        raise


def runtime_parent(parent: Path | None) -> Path:
    if parent is None:
        return Path(tempfile.gettempdir()).resolve()
    return parent.expanduser().resolve()


def reclaim_stale_deployments(parent: Path) -> None:
    """Remove crashed Yoke deployments without touching live owners."""

    for candidate in parent.iterdir():
        owner_pid = runtime_owner_pid(candidate.name)
        if (
            owner_pid is None
            or candidate.is_symlink()
            or not candidate.is_dir()
            or process_is_alive(owner_pid)
        ):
            continue
        shutil.rmtree(candidate, ignore_errors=True)


def runtime_owner_pid(name: str) -> int | None:
    parts = name.split("-", 3)
    if (
        len(parts) != 4
        or parts[0] != "yoke"
        or parts[1]
        not in {
            Provider.CLAUDE.value,
            Provider.CODEX.value,
            Provider.OPENCODE.value,
        }
    ):
        return None
    try:
        pid = int(parts[2])
    except ValueError:
        return None
    return pid if pid > 0 else None


def process_is_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_codex(agent: Agent, deployment: RuntimeDeployment) -> None:
    agents_dir = deployment.root / "agents"
    entries, role_maps = _codex_roles(agent)
    paths = [agents_dir / f"{slug(name)}.toml" for name, _ in entries]
    names = [name for name, _ in entries]
    if len(set(paths)) != len(paths) or len(set(names)) != len(names):
        raise YokeError(
            "Codex subagents compile to colliding role names or artifact paths"
        )
    deployment.codex_role_names = role_maps[id(agent)]
    generated: dict[int, tuple[Path, ...]] = {}
    root_skill_root = deployment.root / "skills"
    generated[id(agent)] = _write_skills(
        direct_inline_skills(agent), Provider.CODEX, root_skill_root
    )
    for role_name, source in entries:
        role_root = deployment.root / "role-skills" / slug(role_name)
        generated[id(source)] = _write_skills(
            direct_inline_skills(source), Provider.CODEX, role_root
        )
    owned = {
        id(owner): _owned_codex_skills(owner, generated[id(owner)])
        for owner in [agent, *(source for _, source in entries)]
    }
    all_skills = tuple(
        dict.fromkeys(path for paths in owned.values() for path in paths)
    )
    deployment.codex_parent_skill_settings = _skill_settings(
        owned[id(agent)], all_skills
    )
    deployment.codex_skill_roots = _codex_skill_roots(agent, generated)
    if generated[id(agent)]:
        deployment.generated_skill_root = root_skill_root
    for (role_name, source), path in zip(entries, paths, strict=True):
        guidance = native_subagents(source, role_names=role_maps[id(source)])
        instructions = instructions_for(source)
        if guidance:
            instructions = f"{instructions}\n\n{guidance}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            codex_agent_toml(
                role_name,
                source,
                instructions=instructions,
                skill_settings=_skill_settings(owned[id(source)], all_skills),
            )
        )
        deployment.codex_agents[role_name] = {
            "description": description_for(role_name, source),
            "config_file": str(path.resolve()),
        }


def _owned_codex_skills(agent: Agent, generated: tuple[Path, ...]) -> tuple[Path, ...]:
    authored = tuple(
        skill.path.expanduser().resolve()
        for skill in agent.skills
        if skill.path is not None
    )
    return tuple(dict.fromkeys((*authored, *generated)))


def _skill_settings(
    enabled: tuple[Path, ...],
    all_skills: tuple[Path, ...],
) -> tuple[tuple[Path, bool], ...]:
    enabled_set = set(enabled)
    return tuple((path, path in enabled_set) for path in all_skills)


def _codex_skill_roots(
    agent: Agent,
    generated: dict[int, tuple[Path, ...]],
) -> tuple[Path, ...]:
    roots: list[Path] = []

    def visit(owner: Agent) -> None:
        roots.extend(
            root
            for skill in owner.skills
            if (root := native_skill_root(skill.path)) is not None
        )
        if generated[id(owner)]:
            roots.append(generated[id(owner)][0].parent.parent)
        for child in owner.subagents.values():
            visit(child)

    visit(agent)
    return tuple(dict.fromkeys(root.resolve() for root in roots))


def _codex_roles(
    agent: Agent,
) -> tuple[list[tuple[str, Agent]], dict[int, dict[str, str]]]:
    entries: list[tuple[str, Agent]] = []
    role_maps: dict[int, dict[str, str]] = {}

    def visit(owner: Agent) -> None:
        mapping: dict[str, str] = {}
        role_maps[id(owner)] = mapping
        for declared_name, child in owner.subagents.items():
            role_name = codex_agent_name(declared_name, child)
            mapping[declared_name] = role_name
            entries.append((role_name, child))
            visit(child)

    visit(agent)
    return entries, role_maps


def _write_claude(agent: Agent, deployment: RuntimeDeployment) -> None:
    plugin = deployment.root / "plugin"
    skills = plugin / "skills"
    if not _write_skills(inline_skills(agent), Provider.CLAUDE, skills):
        return
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": deployment.root.name}))
    deployment.claude_plugin_root = plugin
    deployment.claude_plugin_name = deployment.root.name


def _write_opencode(agent: Agent, deployment: RuntimeDeployment) -> None:
    # OpenCode discovers skills from a config directory the same shape as
    # its own `.opencode/` project convention (skills/<name>/SKILL.md),
    # pointed at via OPENCODE_CONFIG_DIR — no files land in the user's real
    # project, unlike a naive `.opencode/skills/` write into harness.cwd.
    config_dir = deployment.root / "opencode_config"
    skills = config_dir / "skills"
    if _write_skills(inline_skills(agent), Provider.OPENCODE, skills):
        deployment.opencode_config_dir = config_dir
    mcp_servers = option_mapping(agent, "mcp_servers")
    if mcp_servers:
        # Inline config, not a file: OPENCODE_CONFIG_CONTENT is merged over
        # every other config source (global, project, OPENCODE_CONFIG_DIR)
        # at OpenCode's highest precedence, so this doesn't collide with the
        # skills directory above or clobber a real project's opencode.json.
        deployment.opencode_config_content = json.dumps({"mcp": mcp_servers})


def _write_skills(
    skills: tuple[Skill, ...],
    provider: Provider,
    root: Path,
) -> tuple[Path, ...]:
    written: list[Path] = []
    for skill in skills:
        path = root / skill_directory_name(skill) / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            native_skill_text(skill, require_name=provider is Provider.CODEX)
        )
        written.append(path.resolve())
    return tuple(written)
