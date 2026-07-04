from pathlib import Path

from yoke import Agent, Goal, Harness, Skill

agent = Agent(
    instructions="You are a careful maintainer. Make small, safe changes.",
    goal=Goal(objective="Finish the requested implementation safely."),
    skills=(Skill(path=Path("skills/source-grounding")),),
    subagents={
        "reviewer": Agent(
            description="Find correctness and architecture risks.",
            instructions="Review concretely. Prefer file and line evidence.",
        ),
    },
)

harness = Harness(provider="claude", agent=agent, cwd=Path.cwd())
print(harness)
