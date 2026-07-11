"""Readiness helpers."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandCheck:
    """Completed local readiness command."""

    code: int
    stdout: str
    stderr: str

    @property
    def message(self) -> str:
        """Return the first useful output line."""

        return first_line(self.stdout) or first_line(self.stderr)


async def run_command(
    *args: str,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 10,
) -> CommandCheck:
    """Run one local readiness command."""

    process_env = dict(os.environ)
    if env is not None:
        process_env.update(env)
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=process_env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return CommandCheck(
        code=process.returncode or 0,
        stdout=stdout.decode(errors="replace").strip(),
        stderr=stderr.decode(errors="replace").strip(),
    )


def first_line(value: str) -> str:
    """Return the first line from a string."""

    lines = value.splitlines()
    return lines[0] if lines else ""
