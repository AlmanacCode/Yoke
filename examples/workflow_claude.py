"""Run a simple workflow on Claude through Yoke."""

import asyncio
from pathlib import Path

from yoke import Agent, Harness, Permissions, Step, Tools, Workflow
from yoke.providers import Claude


async def main() -> None:
    agent = Agent(
        instructions="You are concise and careful.",
        tools=Tools(read=False, write=False, shell=False, web=False, agent=False),
        permissions=Permissions(approval="never"),
        subagents={
            "reviewer": Agent(
                description="Return one concise review word.",
                instructions="Reply with exactly one lowercase word.",
                tools=Tools(read=False, write=False, shell=False, web=False, agent=False),
                permissions=Permissions(approval="never"),
            ),
        },
    )
    workflow = Workflow(
        name="tiny-review",
        steps=(
            Step(
                name="draft",
                agent="main",
                prompt="Say exactly: yoke",
            ),
            Step(
                name="review",
                agent="reviewer",
                depends_on=("draft",),
                prompt="Review this draft: {draft}. Say exactly: good",
            ),
        ),
    )
    result = await (
        Harness(provider="claude", agent=agent, cwd=Path.cwd())
        .with_adapter(Claude())
        .workflow(workflow)
    )
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
