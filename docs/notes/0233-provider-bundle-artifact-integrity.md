# Provider bundle artifact integrity

2026-07-04

Yoke provider bundles now reject ambiguous artifact output instead of silently dropping or overwriting files.

The recursive subagent skill slice made provider bundles collect inline skills from the whole agent tree. That exposed a collision risk: a root agent and a subagent can both declare an inline skill with the same slug. If the content differs, both compile to the same provider path but mean different things.

Rules now enforced:

- identical recursive inline skills dedupe cleanly
- conflicting recursive inline skills with the same provider path raise `YokeError`
- `Bundle` rejects duplicate artifact paths regardless of which compiler produced them

This keeps provider bundle compilation honest. A bundle is a set of files Yoke can write; two different artifacts cannot own one path.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_artifacts.py tests/test_capabilities.py tests/test_folders.py`
- `PYTHONPATH=src uv run ruff check src/yoke/artifacts.py src/yoke/models.py tests/test_artifacts.py tests/test_capabilities.py`
