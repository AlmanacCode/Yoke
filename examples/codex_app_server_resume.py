"""Resume a persistent Codex app-server thread."""

import asyncio
from pathlib import Path

from yoke import Agent, Harness, Permissions, SessionOptions
from yoke.providers import CodexAppServer


async def main() -> None:
    agent = Agent(
        instructions="Keep replies tiny.",
        permissions=Permissions(access="read", approval="never", network=False),
    )
    first_harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=agent,
        cwd=Path.cwd(),
    ).with_adapter(CodexAppServer(ephemeral=False))
    first = await first_harness.start()
    try:
        await first.run("Remember the word resume-yoke. Reply exactly: stored")
        thread_id = first.id
    finally:
        await first.close()

    second_harness = Harness(
        provider="codex",
        surface="codex_app_server",
        agent=agent,
        cwd=Path.cwd(),
    ).with_adapter(CodexAppServer(ephemeral=False))
    second = await second_harness.start(SessionOptions(resume=thread_id))
    try:
        result = await second.run(
            "What word did I ask you to remember? Reply with only the word."
        )
        print(result.output)
    finally:
        await second.close()


if __name__ == "__main__":
    asyncio.run(main())

