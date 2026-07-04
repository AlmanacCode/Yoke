"""Run a real Claude one-shot through Yoke."""

import asyncio
from pathlib import Path

from yoke import Agent, Goal, Harness, Permissions, Tools
from yoke.providers import Claude


async def main() -> None:
    agent = Agent(
        instructions="You are concise and careful.",
        goal=Goal("Answer the user's request safely."),
        tools=Tools(read=False, write=False, shell=False, web=False, agent=False),
        permissions=Permissions(approval="never"),
    )
    result = await (
        Harness(provider="claude", agent=agent, cwd=Path.cwd())
        .with_adapter(Claude())
        .run("Say exactly: yoke works")
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
