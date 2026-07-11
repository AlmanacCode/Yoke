# Contributing to Yoke

Thanks for helping improve Yoke.

## Development

Yoke requires Python 3.11 or newer. Install the development environment and
run the complete local gate:

```bash
uv sync --all-extras
uv run ruff check .
uv run pytest
uv build
```

Provider live tests may consume account quota and require an existing Claude
Code or Codex login. Unit tests must remain runnable without either login.

## Pull requests

Keep changes focused, add tests for public behavior, and document whether a
provider feature is native, compiled, emulated, or unsupported. Never commit
provider credentials, transcripts, or user workspace data.

By contributing, you agree that your contribution is licensed under the
Apache License 2.0.
