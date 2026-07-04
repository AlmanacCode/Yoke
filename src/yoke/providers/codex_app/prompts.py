"""Prompt assembly for Codex app-server."""

from __future__ import annotations

from typing import Any


def developer_instructions(agent: Any) -> str | None:
    parts: list[str] = []
    if agent.instructions:
        parts.append(agent.instructions)
    skill_text = compiled_skills(agent)
    if skill_text:
        parts.append(skill_text)
    return "\n\n".join(parts) or None


def compiled_skills(agent: Any) -> str | None:
    skills = [skill for skill in agent.skills if skill.instructions]
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
