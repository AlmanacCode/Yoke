"""Codex app-server skill root wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SKILL_FILE = "SKILL.md"


def native_skill_roots(agent: Any) -> tuple[Path, ...]:
    """Return app-server skill roots for packaged Yoke skills.

    Codex app-server scans roots that contain skill folders. A Yoke folder skill
    lives at `skills/<name>/SKILL.md`, so the native root is the containing
    `skills/` directory, not the individual skill directory.
    """

    roots: list[Path] = []
    collect_native_skill_roots(agent, roots)
    deduped: dict[str, Path] = {}
    for root in roots:
        resolved = root.expanduser().resolve()
        deduped[str(resolved)] = resolved
    return tuple(deduped.values())


def collect_native_skill_roots(agent: Any, roots: list[Path]) -> None:
    for skill in getattr(agent, "skills", ()):
        root = native_skill_root(getattr(skill, "path", None))
        if root is not None:
            roots.append(root)
    for subagent in getattr(agent, "subagents", {}).values():
        collect_native_skill_roots(subagent, roots)


def native_skill_root(path: Path | None) -> Path | None:
    if path is None:
        return None
    expanded = path.expanduser()
    if expanded.is_dir() and (expanded / SKILL_FILE).exists():
        return expanded.parent
    if expanded.is_file() and expanded.name == SKILL_FILE:
        return expanded.parent.parent
    return None


def is_native_skill_path(path: Path | None) -> bool:
    return native_skill_root(path) is not None

