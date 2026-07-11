# CodeAlmanac feature report integration

CodeAlmanac already imports Yoke as the default harness package through its editable `pyproject.toml` source dependency. The integration seam is `src/codealmanac/integrations/harnesses/yoke/` in the CodeAlmanac repo.

The product boundary remains CodeAlmanac-owned:

- `RunHarnessRequest` carries CodeAlmanac request data.
- `HarnessGoal` is CodeAlmanac's goal value and is translated into `yoke.Goal` only inside the adapter.
- Lifecycle workflows still own init, ingest, garden, job logging, mutation safety, and reindexing.
- Yoke owns provider surface execution, readiness, status, and capability metadata.

This slice updated the CodeAlmanac bridge to preserve Yoke feature report details on `HarnessFeatureSupport`:

- `lowering`
- `recipes`
- `evidence`

The immediate reason was the new Yoke `Plan.reports` and the clarified Claude goal semantics. CodeAlmanac doctor/status can now carry the same feature detail without importing Yoke models outside the adapter boundary.

The important semantic distinction now survives the bridge:

- Codex app-server reports native readable/mutable thread goal state.
- Claude SDK reports `/goal` as a provider-owned loop, not readable or mutable goal state.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_yoke_harness_adapter.py tests/test_diagnostics.py`
- `PYTHONPATH=src uv run ruff check src/codealmanac/engine/harnesses/results.py src/codealmanac/integrations/harnesses/yoke/mapper.py tests/test_yoke_harness_adapter.py tests/test_diagnostics.py`
