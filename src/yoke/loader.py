"""Folder loader for Yoke agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yoke.models import (
    Agent,
    Collection,
    Goal,
    Permissions,
    Skill,
    Step,
    Tools,
    Workflow,
)

AGENT_FILE = "agent.yaml"
COLLECTION_FILE = "yoke.yaml"
INSTRUCTIONS_FILE = "instructions.md"
INSTRUCTIONS_DIR = "instructions"
SKILL_FILE = "SKILL.md"
SKILLS_DIR = "skills"
SUBAGENTS_DIR = "subagents"
WORKFLOWS_DIR = "workflows"
WORKFLOW_PROGRAM_FILE = "workflow.py"
WORKFLOW_SCRIPT_FILE = "script.js"


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
        root=root,
        instructions=instructions or config.get("instructions"),
        description=config.get("description"),
        model=optional_inherit(config.get("model")),
        effort=config.get("effort"),
        goal=parse_goal(goal),
        tools=Tools(**config["tools"])
        if isinstance(config.get("tools"), dict)
        else Tools(),
        permissions=Permissions(**config["permissions"])
        if isinstance(config.get("permissions"), dict)
        else Permissions(),
        skills=tuple(skills),
        subagents=subagents,
        workflows=workflows,
        options=config.get("options", {}),
    )


def load_collection(path: str | Path) -> Collection:
    """Load an agent collection from ``yoke.yaml``."""

    root = Path(path)
    config = read_yaml(root / COLLECTION_FILE)
    agents = config.get("agents")
    if not isinstance(agents, dict):
        raise ValueError(f"{root / COLLECTION_FILE} must define an agents mapping")
    paths: dict[str, Path] = {}
    for name, agent_path in agents.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("collection agent names must be non-empty strings")
        if not isinstance(agent_path, str) or not agent_path.strip():
            raise ValueError(f"collection agent {name!r} must map to a path string")
        paths[name] = Path(agent_path)
    default_provider = config.get("default_provider")
    if default_provider is not None and not isinstance(default_provider, str):
        raise ValueError("default_provider must be a string")
    return Collection(
        root=root,
        agents=paths,
        default_provider=default_provider,
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


def parse_goal(value: Any) -> Goal | None:
    if isinstance(value, str):
        return Goal(value)
    if isinstance(value, dict):
        return Goal(**value)
    return None


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
        data["name"] = path_identity(child.stem, data.get("name"), child, "workflow")
        workflow = Workflow(**data)
        workflows[workflow.name] = workflow
    for child in sorted(path.iterdir()):
        if child.is_dir():
            workflow = load_markdown_workflow(child)
            workflows[workflow.name] = workflow
    return workflows


def load_markdown_workflow(path: Path) -> Workflow:
    """Load workflows/<name>/*.md as path-derived workflow steps."""

    steps: list[dict[str, Any]] = []
    description: str | None = None
    config = read_yaml(path / "workflow.yaml")
    workflow_name = path_identity(
        path.name,
        config.get("name"),
        path / "workflow.yaml",
        "workflow",
    )
    if isinstance(config.get("description"), str):
        description = config["description"]
    script_path = path / WORKFLOW_SCRIPT_FILE
    program_path = path / WORKFLOW_PROGRAM_FILE
    if program_path.exists():
        return Workflow(
            name=workflow_name,
            description=description,
            language="python",
            program_path=program_path,
            args=config.get("args"),
        )
    if script_path.exists():
        return Workflow(
            name=workflow_name,
            description=description,
            language=str(config.get("language") or "javascript"),
            script=script_path.read_text().strip(),
            args=config.get("args"),
            resume_from_run_id=config.get("resume_from_run_id")
            or config.get("resumeFromRunId"),
        )
    if config.get("script_path") is not None or config.get("scriptPath") is not None:
        return Workflow(
            name=workflow_name,
            description=description,
            language=str(config.get("language") or "javascript"),
            script_path=Path(str(config.get("script_path") or config["scriptPath"])),
            native_name=config.get("native_name") or config.get("nativeName"),
            args=config.get("args"),
            resume_from_run_id=config.get("resume_from_run_id")
            or config.get("resumeFromRunId"),
        )
    if config.get("native_name") is not None or config.get("nativeName") is not None:
        return Workflow(
            name=workflow_name,
            description=description,
            language=str(config.get("language") or "javascript"),
            native_name=str(config.get("native_name") or config["nativeName"]),
            args=config.get("args"),
            resume_from_run_id=config.get("resume_from_run_id")
            or config.get("resumeFromRunId"),
        )
    for child in sorted(path.glob("*.md")):
        frontmatter, body = read_markdown_with_frontmatter(child)
        if child.name == "README.md" and not body:
            continue
        step_name = path_identity(child.stem, frontmatter.get("name"), child, "step")
        step: dict[str, Any] = {
            "name": step_name,
            "agent": str(frontmatter.get("agent") or "main"),
            "prompt": body,
        }
        depends_on = frontmatter.get("depends_on", frontmatter.get("depends"))
        if depends_on is not None:
            step["depends_on"] = tuple_list(depends_on)
        output_schema = frontmatter.get("output_schema", frontmatter.get("schema"))
        if output_schema is not None:
            step["output_schema"] = output_schema
        if frontmatter.get("run") is not None:
            step["run"] = frontmatter["run"]
        steps.append(step)
    if not steps:
        raise ValueError(f"{path} must contain at least one markdown workflow step")
    return Workflow(
        name=workflow_name,
        description=description,
        steps=tuple(Step(**step) for step in steps),
    )


def path_identity(
    expected: str,
    configured: Any,
    path: Path,
    kind: str,
) -> str:
    """Return the path-derived identity and reject silent metadata renames."""

    if configured is None:
        return expected
    if str(configured) == expected:
        return expected
    raise ValueError(
        f"{path} cannot rename {kind} {expected!r} to {configured!r}; "
        "folder workflow identity comes from the path"
    )


def tuple_list(value: Any) -> tuple[str, ...]:
    """Normalize scalar or list YAML values into a tuple of strings."""

    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    raise ValueError("depends_on must be a string or list of strings")
