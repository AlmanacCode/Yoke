from __future__ import annotations

from yoke import Agent
from yoke.models import Access, Permissions
from yoke.providers.opencode.agents import opencode_agent_files, opencode_agent_markdown


def test_opencode_agent_files_compile_direct_subagents() -> None:
    agent = Agent(
        instructions="Coordinate the work.",
        subagents={
            "docs_researcher": Agent(
                description="Documentation specialist.",
                instructions="Use primary docs and return links.",
                model="gpt-5.4-mini",
            )
        },
    )

    files = opencode_agent_files(agent)

    assert len(files) == 1
    assert files[0].name == "docs_researcher"
    assert files[0].path.as_posix() == ".opencode/agents/docs_researcher.md"
    assert files[0].text == opencode_agent_markdown(
        "docs_researcher", agent.subagents["docs_researcher"]
    )


def test_opencode_agent_markdown_renders_frontmatter_and_body() -> None:
    # Default Permissions() is access=READ, network=False, so the default
    # subagent below also gets a permission: block — matching how
    # codex_agent_toml() already sandboxes a default-permissions subagent
    # to "read-only" rather than leaving it unrestricted.
    subagent = Agent(
        description="Documentation specialist.",
        instructions="Use primary docs and return links.",
        model="gpt-5.4-mini",
    )

    text = opencode_agent_markdown("docs_researcher", subagent)

    assert text == (
        "---\n"
        'description: "Documentation specialist."\n'
        "mode: subagent\n"
        'model: "gpt-5.4-mini"\n'
        "permission:\n"
        "  write: deny\n"
        "  edit: deny\n"
        "  apply_patch: deny\n"
        "  bash: deny\n"
        "  webfetch: deny\n"
        "  websearch: deny\n"
        "---\n"
        "\n"
        "Use primary docs and return links.\n"
    )


def test_opencode_agent_markdown_omits_permission_block_for_full_access() -> None:
    subagent = Agent(
        instructions="do anything",
        permissions=Permissions(access=Access.FULL, network=True),
    )

    text = opencode_agent_markdown("unrestricted", subagent)

    assert "permission:" not in text


def test_opencode_agent_markdown_write_access_allows_edit_but_not_bash() -> None:
    subagent = Agent(
        instructions="edit only",
        permissions=Permissions(access=Access.WRITE, network=True),
    )

    text = opencode_agent_markdown("editor", subagent)

    assert "permission:\n  bash: deny\n" in text
    assert "edit: deny" not in text
    assert "write: deny" not in text


def test_opencode_agent_markdown_falls_back_without_description_or_model() -> None:
    subagent = Agent(instructions="Review the patch for bugs.")

    text = opencode_agent_markdown("reviewer", subagent)

    assert 'description: "Yoke subagent reviewer."' in text
    assert "mode: subagent" in text
    assert "model:" not in text
    assert text.endswith("Review the patch for bugs.\n")


def test_opencode_agent_files_ignores_nested_subagents_of_subagents() -> None:
    agent = Agent(
        instructions="root",
        subagents={
            "planner": Agent(
                instructions="plan",
                subagents={"nested": Agent(instructions="should not compile")},
            )
        },
    )

    files = opencode_agent_files(agent)

    assert [file.name for file in files] == ["planner"]
