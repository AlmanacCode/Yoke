"""Claude local plugin mapping for Yoke folders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SKILL_FILE = "SKILL.md"
SKILLS_DIR = "skills"


def plugin_paths(agent: Any) -> tuple[Path, ...]:
    """Return Claude local plugin roots for native Yoke folder skills."""

    roots: list[Path] = []
    collect_plugin_paths(agent, roots)
    deduped: dict[str, Path] = {}
    for root in roots:
        resolved = root.expanduser().resolve()
        deduped[str(resolved)] = resolved
    return tuple(deduped.values())


def collect_plugin_paths(agent: Any, roots: list[Path]) -> None:
    root = getattr(agent, "root", None)
    if is_plugin_root(root):
        roots.append(root)
    for skill in getattr(agent, "skills", ()):
        root = plugin_root_for_skill(getattr(skill, "path", None))
        if root is not None:
            roots.append(root)
    for subagent in getattr(agent, "subagents", {}).values():
        collect_plugin_paths(subagent, roots)


def is_plugin_root(path: Path | None) -> bool:
    return path is not None and (path.expanduser() / SKILLS_DIR).is_dir()


def plugin_root_for_skill(path: Path | None) -> Path | None:
    if path is None:
        return None
    expanded = path.expanduser()
    if expanded.is_dir() and (expanded / SKILL_FILE).exists():
        skills_dir = expanded.parent
        if skills_dir.name == SKILLS_DIR:
            return skills_dir.parent
    if expanded.is_file() and expanded.name == SKILL_FILE:
        skills_dir = expanded.parent.parent
        if skills_dir.name == SKILLS_DIR:
            return skills_dir.parent
    return None


def is_plugin_skill_path(path: Path | None) -> bool:
    return plugin_root_for_skill(path) is not None

