"""Small Codex CLI JSONL bridge."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from yoke.errors import YokeError

ORIGINATOR_ENV = "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
YOKE_ORIGINATOR = "yoke_python"


class CodexCli:
    """Run `codex exec --json` and yield decoded events."""

    def __init__(
        self,
        executable: str = "codex",
        env: dict[str, str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.executable = executable
        self.env = env
        self.config = config or {}

    async def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        thread_id: str | None = None,
        model: str | None = None,
        sandbox: str | None = None,
        approval: str | None = None,
        effort: str | None = None,
        network: bool | None = None,
        web_search: str | None = None,
        output_schema: dict[str, Any] | None = None,
        skip_git_repo_check: bool = False,
        additional_directories: tuple[Path, ...] = (),
    ) -> AsyncIterator[dict[str, Any]]:
        schema_path: Path | None = None
        try:
            args = [self.executable, "exec", "--json", "--cd", str(cwd)]
            if model:
                args.extend(["--model", model])
            if sandbox:
                args.extend(["--sandbox", sandbox])
            if skip_git_repo_check:
                args.append("--skip-git-repo-check")
            for directory in additional_directories:
                args.extend(["--add-dir", str(directory)])
            for override in config_overrides(self.config):
                args.extend(["--config", override])
            if approval:
                args.extend(["--config", f"approval_policy={json.dumps(approval)}"])
            if effort:
                args.extend(
                    [
                        "--config",
                        f"model_reasoning_effort={json.dumps(effort)}",
                    ]
                )
            if network is not None:
                args.extend(
                    [
                        "--config",
                        f"sandbox_workspace_write.network_access={str(network).lower()}",
                    ]
                )
            if web_search:
                args.extend(["--config", f"web_search={json.dumps(web_search)}"])
            if output_schema is not None:
                schema_path = write_schema(output_schema)
                args.extend(["--output-schema", str(schema_path)])
            if thread_id:
                args.extend(["resume", thread_id])
            args.append("-")

            env = dict(os.environ)
            if self.env is not None:
                env.update(self.env)
            env.setdefault(ORIGINATOR_ENV, YOKE_ORIGINATOR)

            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None

            process.stdin.write(prompt.encode())
            await process.stdin.drain()
            process.stdin.close()

            async for raw in process.stdout:
                line = raw.decode().strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise YokeError(f"Codex emitted invalid JSONL: {line}") from exc

            code = await process.wait()
            if code != 0:
                stderr = (await process.stderr.read()).decode().strip()
                raise YokeError(f"codex exec exited with code {code}: {stderr}")
        finally:
            if schema_path is not None:
                schema_path.unlink(missing_ok=True)


def write_schema(schema: dict[str, Any]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="yoke-codex-schema-",
        delete=False,
    )
    with handle:
        json.dump(schema, handle)
    return Path(handle.name)


def config_overrides(config: dict[str, Any]) -> list[str]:
    overrides: list[str] = []
    flatten_config(config, "", overrides)
    return overrides


def flatten_config(value: Any, prefix: str, overrides: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flatten_config(child, path, overrides)
        return
    if not prefix:
        raise ValueError("Codex config overrides must be keyed")
    overrides.append(f"{prefix}={json.dumps(value)}")
