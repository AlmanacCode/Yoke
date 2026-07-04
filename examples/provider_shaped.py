"""Provider-shaped Yoke sketch."""

from pathlib import Path

from yoke import Agent, Goal, Harness, Permissions, Tools

agent = Agent(
    instructions="You are a careful maintainer.",
    goal=Goal("Finish the requested implementation safely.", token_budget=200_000),
    tools=Tools(read=True, write=True, shell=True, agent=True),
    permissions=Permissions(access="write", approval="ask", network=False),
)

harness = Harness(provider="claude", agent=agent, cwd=Path.cwd())

# result = await harness.run("Implement the bundle loader.")
