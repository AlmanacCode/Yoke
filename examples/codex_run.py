"""Run a real Codex one-shot through Yoke."""

import asyncio
from pathlib import Path

from yoke import Agent, Harness, Permissions, Tools
from yoke.providers import Codex


async def main() -> None:
    agent = Agent(
        instructions="You are concise and careful.",
        tools=Tools(read=False, write=False, shell=False, web=False, agent=False),
        permissions=Permissions(access="read", approval="never", network=False),
    )
    result = await (
        Harness(provider="codex", agent=agent, cwd=Path.cwd())
        .with_adapter(Codex())
        .run("Say exactly: yoke codex works")
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
