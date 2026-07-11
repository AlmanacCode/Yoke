"""Run a real resumable Codex CLI session through Yoke."""

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
    first = await (
        Harness(provider="codex", agent=agent, cwd=Path.cwd())
        .with_adapter(Codex())
        .run("Remember the word yoke. Say exactly: first")
    )
    if first.session is None:
        raise RuntimeError("Codex did not return a resumable session")
    second = await first.session.run(
        "What word did I ask you to remember? Say only it."
    )
    print(first.output)
    print(second.output)


if __name__ == "__main__":
    asyncio.run(main())
