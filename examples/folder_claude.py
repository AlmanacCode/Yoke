"""Load an agent folder and run it on Claude."""

import asyncio
from pathlib import Path

from yoke import Agent, Harness
from yoke.providers import Claude


async def main() -> None:
    agent = Agent.from_folder(Path(__file__).parent / "folder_agent").model_copy(
        update={"goal": None}
    )
    result = await (
        Harness(provider="claude", agent=agent, cwd=Path.cwd())
        .with_adapter(Claude())
        .workflow("tiny")
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
