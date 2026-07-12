"""Synchronous `opencode serve` process spawn.

Mirrors codex_app/process.py's precedent: a synchronous, thread-backed
process wrapper that async adapter methods bridge to via `asyncio.to_thread`,
rather than a native asyncio subprocess rewrite. This lets the polling-based
progress design (progress.py) share the same threading model.
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from yoke.errors import YokeError

OPENCODE_SERVER_STARTUP_TIMEOUT_SECONDS = 10.0
OPENCODE_SERVER_TERMINATE_TIMEOUT_SECONDS = 5.0
_LISTENING_PATTERN = re.compile(r"listening on http://127\.0\.0\.1:(\d+)")


class OpencodeServerStartupError(YokeError):
    pass


class OpencodeServerProcess:
    def __init__(self, process: subprocess.Popen[str], base_url: str) -> None:
        self.process = process
        self.base_url = base_url

    def __enter__(self) -> OpencodeServerProcess:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.terminate()

    def terminate(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=OPENCODE_SERVER_TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=OPENCODE_SERVER_TERMINATE_TIMEOUT_SECONDS)


def start_opencode_server(
    command: str,
    cwd: Path,
    startup_timeout_seconds: float = OPENCODE_SERVER_STARTUP_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> OpencodeServerProcess:
    # Windows: npm-installed opencode ships as a .cmd/.ps1 shim, and
    # subprocess.Popen(shell=False) can't launch a bare command name through
    # CreateProcess the way a shell would.
    resolved = shutil.which(command) or command
    # subprocess.Popen(env=...) replaces the environment wholesale, not
    # merges it — passing a partial dict (e.g. just OPENCODE_CONFIG_DIR)
    # would silently strip HOME/PATH and degrade opencode to whatever
    # providers/config it can find without them. Merge onto a copy of the
    # real environment instead, matching codex_app/process.py's precedent.
    process_env = dict(os.environ)
    if env is not None:
        process_env.update(env)
    process = subprocess.Popen(
        (resolved, "serve", "--port", "0"),
        cwd=cwd,
        env=process_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base_url = _wait_for_listening(process, startup_timeout_seconds)
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=OPENCODE_SERVER_TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    return OpencodeServerProcess(process=process, base_url=base_url)


def _wait_for_listening(process: subprocess.Popen[str], timeout_seconds: float) -> str:
    assert process.stdout is not None
    lines: queue.Queue[str | None] = queue.Queue()

    def _reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    # A background thread draining stdout, not a blocking readline() loop:
    # readline() blocks past any wall-clock deadline check between calls, and
    # select() on pipes isn't available on Windows.
    threading.Thread(target=_reader, daemon=True).start()

    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OpencodeServerStartupError(
                "opencode serve did not report a listening port in time"
            )
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty as error:
            raise OpencodeServerStartupError(
                "opencode serve did not report a listening port in time"
            ) from error
        if line is None:
            raise OpencodeServerStartupError(
                "opencode serve exited before it started listening"
            )
        match = _LISTENING_PATTERN.search(line)
        if match is not None:
            return f"http://127.0.0.1:{match.group(1)}"
