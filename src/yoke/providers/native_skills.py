"""Shared rendering for runtime-native inline skill files."""

from __future__ import annotations

import re

import yaml

from yoke.errors import YokeError
from yoke.models import Agent, Skill


def inline_skills(agent: Agent) -> tuple[Skill, ...]:
    """Collect unique text-backed skills across an agent tree."""

    found: dict[str, Skill] = {}
    for skill in agent.skills:
        if skill.instructions is not None:
            _add(found, skill)
    for subagent in agent.subagents.values():
        for skill in inline_skills(subagent):
            _add(found, skill)
    return tuple(found.values())


def direct_inline_skills(agent: Agent) -> tuple[Skill, ...]:
    """Return only skills owned by this agent, excluding descendant roles."""

    found: dict[str, Skill] = {}
    for skill in agent.skills:
        if skill.instructions is not None:
            _add(found, skill)
    return tuple(found.values())


def skill_directory_name(skill: Skill) -> str:
    value = skill.name or "skill"
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-") or "skill"


def native_skill_text(skill: Skill, *, require_name: bool) -> str:
    name = skill.name or "skill"
    frontmatter: dict[str, str] = {
        "description": skill.description or f"Yoke skill {name}."
    }
    if require_name or skill.name:
        frontmatter["name"] = name
    return (
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n"
        f"{(skill.instructions or '').strip()}\n"
    )


def _add(found: dict[str, Skill], skill: Skill) -> None:
    path = skill_directory_name(skill)
    existing = found.get(path)
    if existing is not None and existing != skill:
        raise YokeError(
            "inline skills compile to the same provider path with different "
            f"content: {path}"
        )
    found[path] = skill
