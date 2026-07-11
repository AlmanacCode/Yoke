"""Run one real Codex app-server turn through Yoke."""

import asyncio
from pathlib import Path

from yoke import Agent, Harness, Permissions
from yoke.providers import CodexAppServer


async def main() -> None:
    agent = Agent(
        instructions="Reply with exactly: yoke app server works",
        permissions=Permissions(access="read", approval="never", network=False),
    )
    result = await (
        Harness(
            provider="codex",
            surface="codex_app_server",
            agent=agent,
            cwd=Path.cwd(),
        )
        .with_adapter(CodexAppServer())
        .run("Say the required phrase.")
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
