"""Prompt assembly for Codex app-server."""

from __future__ import annotations

from typing import Any

from yoke.providers.codex_app.skills import is_native_skill_path
from yoke.providers.compiled import compiled_subagents


def developer_instructions(agent: Any) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    subagent_text = compiled_subagents(agent)
    if subagent_text:
        parts.append(subagent_text)
    skill_text = compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    return "\n\n".join(parts) or None


def compiled_skills(agent: Any) -> str | None:
    skills = [
        skill
        for skill in agent.skills
        if skill.instructions and not is_native_skill_path(skill.path)
    ]
    if not skills:
        return None
    sections = [
        "Available Yoke skills follow. Treat each skill as optional procedure "
        "context; use it only when the user request matches its description."
    ]
    for skill in skills:
        header = skill.name or "skill"
        description = f"\nDescription: {skill.description}" if skill.description else ""
        sections.append(f"## {header}{description}\n\n{skill.instructions}")
    return "\n\n".join(sections)
