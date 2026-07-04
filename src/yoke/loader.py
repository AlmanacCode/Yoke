"""Folder loader for Yoke agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yoke.models import Agent, Goal, Permissions, Skill, Step, Tools, Workflow

AGENT_FILE = "agent.yaml"
INSTRUCTIONS_FILE = "instructions.md"
INSTRUCTIONS_DIR = "instructions"
SKILL_FILE = "SKILL.md"
SKILLS_DIR = "skills"
SUBAGENTS_DIR = "subagents"
WORKFLOWS_DIR = "workflows"


def load(path: str | Path) -> Agent:
    """Load an agent folder.

    This is intentionally small. It establishes folder parity without yet
    compiling provider-specific artifacts.
    """

    root = Path(path)
    config = read_yaml(root / AGENT_FILE)
    instructions = read_instructions(root)
    skills = load_skills(root / SKILLS_DIR)
    subagents = load_subagents(root / SUBAGENTS_DIR)
    workflows = load_workflows(root / WORKFLOWS_DIR)
    goal = config.get("goal")
    return Agent(
        instructions=instructions or config.get("instructions"),
        description=config.get("description"),
        model=optional_inherit(config.get("model")),
        effort=config.get("effort"),
        goal=Goal(**goal) if isinstance(goal, dict) else None,
        tools=Tools(**config["tools"]) if isinstance(config.get("tools"), dict) else Tools(),
        permissions=Permissions(**config["permissions"])
        if isinstance(config.get("permissions"), dict)
        else Permissions(),
        skills=tuple(skills),
        subagents=subagents,
        workflows=workflows,
        options=config.get("options", {}),
    )


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def optional_inherit(value: Any) -> Any:
    if value == "inherit":
        return None
    return value


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text().strip()
    return text or None


def read_instructions(root: Path) -> str | None:
    parts: list[str] = []
    root_text = read_optional_text(root / INSTRUCTIONS_FILE)
    if root_text:
        parts.append(root_text)
    directory = root / INSTRUCTIONS_DIR
    if directory.exists():
        for child in sorted(directory.glob("*.md")):
            text = read_optional_text(child)
            if text:
                parts.append(text)
    return "\n\n".join(parts) or None


def load_skills(path: Path) -> list[Skill]:
    if not path.exists():
        return []
    skills: list[Skill] = []
    for child in sorted(path.iterdir()):
        if child.is_dir():
            skills.append(load_packaged_skill(child))
        elif child.is_file() and child.suffix == ".md":
            skills.append(load_markdown_skill(child, name=child.stem))
    return skills


def load_packaged_skill(path: Path) -> Skill:
    skill_path = path / SKILL_FILE
    if not skill_path.exists():
        return Skill.from_path(path, name=path.name)
    frontmatter, body = read_markdown_with_frontmatter(skill_path)
    return Skill(
        name=str(frontmatter.get("name") or path.name),
        description=description_for_skill(frontmatter, body, path.name),
        path=path,
        instructions=body,
    )


def load_markdown_skill(path: Path, name: str) -> Skill:
    frontmatter, body = read_markdown_with_frontmatter(path)
    return Skill(
        name=str(frontmatter.get("name") or name),
        description=description_for_skill(frontmatter, body, name),
        path=path,
        instructions=body,
    )


def read_markdown_with_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text().strip()
    if not text.startswith("---\n"):
        return {}, text
    try:
        _, yaml_text, body = text.split("---", 2)
    except ValueError:
        return {}, text
    data = yaml.safe_load(yaml_text)
    if data is None:
        frontmatter: dict[str, Any] = {}
    elif isinstance(data, dict):
        frontmatter = data
    else:
        raise ValueError(f"{path} frontmatter must be a YAML mapping")
    return frontmatter, body.strip()


def description_for_skill(frontmatter: dict[str, Any], body: str, name: str) -> str:
    description = frontmatter.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    for line in body.splitlines():
        stripped = line.strip().lstrip("#>*- ").strip()
        if stripped and not stripped.startswith("```"):
            return stripped
    return f"Instructions for the {name} skill."


def load_subagents(path: Path) -> dict[str, Agent]:
    if not path.exists():
        return {}
    agents: dict[str, Agent] = {}
    for child in sorted(path.iterdir()):
        if child.is_dir():
            agents[child.name] = load(child)
    return agents


def load_workflows(path: Path) -> dict[str, Workflow]:
    if not path.exists():
        return {}
    workflows: dict[str, Workflow] = {}
    for child in sorted(path.glob("*.yaml")) + sorted(path.glob("*.yml")):
        data = read_yaml(child)
        name = str(data.get("name") or child.stem)
        steps = tuple(Step(**step) for step in data.get("steps", []))
        workflows[name] = Workflow(
            name=name,
            description=data.get("description"),
            steps=steps,
        )
    return workflows
