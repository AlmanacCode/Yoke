"""Read, set, and clear a native Codex app-server goal."""

import asyncio
from pathlib import Path

from yoke import Agent, Goal, Harness, Permissions


async def main() -> None:
    agent = Agent(
        instructions="Keep replies tiny.",
        permissions=Permissions(access="read", approval="never", network=False),
    )
    session = await Harness(
        provider="codex",
        surface="codex_app_server",
        agent=agent,
        cwd=Path.cwd(),
    ).start()
    try:
        session = await session.set_goal(Goal("prove goal read", token_budget=1234))
        goal = await session.get_goal()
        print(goal)
        session = await session.clear_goal()
        print(await session.get_goal())
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())

