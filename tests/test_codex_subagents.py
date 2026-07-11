from __future__ import annotations

from yoke import Agent, CodexAgentSettings, Effort, Goal, Tools
from yoke.models import Access, Permissions, Skill
from yoke.providers.codex import codex_prompt
from yoke.providers.codex_agents import (
    codex_agent_files,
    codex_agent_settings,
    codex_agent_settings_toml,
)
from yoke.providers.codex_app.prompts import developer_instructions


def test_codex_cli_prompt_compiles_agent_and_subagents() -> None:
    agent = Agent(
        instructions="You are the root maintainer.",
        goal=Goal("Ship safely."),
        subagents={
            "reviewer": Agent(
                description="Find correctness issues.",
                instructions="Review the patch for bugs.",
                model="review-model",
                effort=Effort.HIGH,
                tools=Tools(read=True, shell=True),
            )
        },
    )

    prompt = codex_prompt("Implement the loader.", agent.goal, agent)

    assert "You are the root maintainer." in prompt
    assert "Available Yoke subagents follow." in prompt
    assert "not native delegated processes" in prompt
    assert "## reviewer" in prompt
    assert "Description: Find correctness issues." in prompt
    assert "Runtime hints: model=review-model, effort=high" in prompt
    assert "Tools: read, shell" in prompt
    assert "Instructions:\nReview the patch for bugs." in prompt
    assert "Goal: Ship safely." in prompt
    assert "User request:\nImplement the loader." in prompt


def test_codex_app_server_developer_instructions_compile_subagents() -> None:
    agent = Agent(
        instructions="You are the app-server root agent.",
        subagents={
            "researcher": Agent(
                description="Research provider behavior.",
                instructions="Prefer primary sources.",
                model="gpt-5.4-mini",
            )
        },
    )

    instructions = developer_instructions(agent)

    assert instructions is not None
    assert "You are the app-server root agent." in instructions
    assert "Available native Codex subagents follow." in instructions
    assert "exact `agent_type`" in instructions
    assert "Never simulate these roles" in instructions
    assert "## researcher" in instructions
    assert "Description: Research provider behavior." in instructions
    assert 'spawn_agent(agent_type="researcher", fork_turns="none")' in instructions
    assert "Prefer primary sources." not in instructions
    assert "gpt-5.4-mini" not in instructions


def test_codex_custom_agent_files_compile_direct_subagents() -> None:
    agent = Agent(
        instructions="Coordinate the work.",
        subagents={
            "docs_researcher": Agent(
                description="Documentation specialist.",
                instructions="Use primary docs and return links.",
                model="gpt-5.4-mini",
                effort=Effort.MEDIUM,
                permissions=Permissions(access=Access.READ),
                skills=(Skill.from_path("/Users/me/.agents/skills/docs/SKILL.md"),),
                options={
                    "nickname_candidates": ["Atlas", "Echo"],
                    "mcp_servers": {
                        "openaiDeveloperDocs": {
                            "url": "https://developers.openai.com/mcp",
                            "startup_timeout_sec": 20,
                        }
                    },
                },
            )
        },
    )

    files = codex_agent_files(agent)

    assert len(files) == 1
    assert files[0].name == "docs_researcher"
    assert files[0].path.as_posix() == ".codex/agents/docs_researcher.toml"
    assert 'name = "docs_researcher"' in files[0].text
    assert 'description = "Documentation specialist."' in files[0].text
    assert 'model = "gpt-5.4-mini"' in files[0].text
    assert 'model_reasoning_effort = "medium"' in files[0].text
    assert 'sandbox_mode = "read-only"' in files[0].text
    assert 'nickname_candidates = ["Atlas", "Echo"]' in files[0].text
    assert (
        'developer_instructions = """\nUse primary docs and return links.\n"""'
        in files[0].text
    )
    assert "[mcp_servers.openaiDeveloperDocs]" in files[0].text
    assert 'url = "https://developers.openai.com/mcp"' in files[0].text
    assert "startup_timeout_sec = 20" in files[0].text
    assert "[[skills.config]]" in files[0].text
    assert 'path = "/Users/me/.agents/skills/docs/SKILL.md"' in files[0].text
    assert "enabled = true" in files[0].text


def test_codex_agent_settings_accept_typed_and_dict_options() -> None:
    typed = Agent(
        instructions="Coordinate.",
        options={"codex_agents": CodexAgentSettings(max_threads=6, max_depth=1)},
    )
    raw = Agent(
        instructions="Coordinate.",
        options={
            "codexAgents": {
                "maxThreads": 4,
                "jobMaxRuntimeSeconds": 1800,
            }
        },
    )

    typed_settings = codex_agent_settings(typed)
    raw_settings = codex_agent_settings(raw)

    assert typed_settings == CodexAgentSettings(max_threads=6, max_depth=1)
    assert raw_settings == CodexAgentSettings(
        max_threads=4,
        job_max_runtime_seconds=1800,
    )
    assert codex_agent_settings_toml(raw_settings) == (
        "[agents]\n"
        "max_threads = 4\n"
        "job_max_runtime_seconds = 1800\n"
    )
