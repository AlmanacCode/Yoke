# Codex Python SDK live install and fork smoke

The local Yoke environment initially reported `codex_python_sdk` as unavailable because `openai_codex` was not installed.

Install attempt:

- `uv pip install -e ../openai-codex/sdk/python` failed because the SDK tried to download `openai-codex-cli-bin==0.137.0a4` and the machine had only about 80 MiB free.
- `uv pip install --no-deps -e ../openai-codex/sdk/python` succeeded and installed the local cloned SDK as `openai-codex==0.0.0.dev0`.
- Readiness then reported `openai_codex available (0.0.0-dev)`.

Runtime issue:

The no-deps install did not include the SDK's bundled `codex_cli_bin`, so the first live SDK run failed with:

`Unable to locate the pinned Codex runtime. Install the published SDK build with its openai-codex-cli-bin dependency, or set CodexConfig.codex_bin explicitly.`

Yoke fix:

`CodexPythonSdk._codex_config()` now passes `CodexConfig(codex_bin=<existing codex binary>)` when the SDK exposes `CodexConfig` and `shutil.which("codex")` finds the existing local CLI. This keeps Yoke on the SDK surface while using the already-authenticated local Codex runtime.

Live run result:

- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-codex-sdk`
- result: `codex_python_sdk run: succeeded: yoke-sdk-smoke`

Fork issue:

The first live SDK fork failed with `no rollout found for thread id ...`. The SDK's own tests describe fork as working for a persisted rollout. Yoke was starting SDK threads with `ephemeral=True` whenever there was no goal, so a normal started session was not forkable.

Yoke fix:

`CodexPythonSdk._thread()` now starts SDK threads with `ephemeral=False`. This matches Yoke's public `Session.fork()` contract for `codex_python_sdk`.

Live fork result:

- `PYTHONPATH=src uv run python scripts/smoke_harnesses.py --run-codex-sdk-fork`
- result: `codex_python_sdk fork: source=<thread-id> fork=<different-thread-id>`

Verification:

- `PYTHONPATH=src uv run pytest tests/test_codex_python_sdk.py` -> 9 passed
- `uv run ruff check src/yoke/providers/codex_sdk.py tests/test_codex_python_sdk.py` -> all checks passed

Remaining operational note:

The machine disk is critically full. A full dependency install with the SDK's pinned runtime still needs disk cleanup before it can succeed.
