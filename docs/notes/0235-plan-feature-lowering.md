# Plan feature lowering

Yoke now exposes feature-level support rows on `Plan`.

`Harness.plan()` and `Session.plan()` already selected a provider surface from requested features. The missing piece was the explanation of how each requested feature is lowered on that surface. `Plan.reports` now returns `FeatureReport` rows for the selected surface, and `Plan.report(feature)` returns one requested feature row.

This keeps execution ports unchanged. Adapters still own provider calls. The plan object now joins the selected `Profile` with the same lowering, recipe, and evidence tables used by `report_for(...)`.

The important product effect is that goals, workflows, subagents, and skills are inspectable before execution:

- `goal` can show native app-server thread goal state, compiled prompt context, or unsupported provider state.
- `goal_loop` remains a separate feature from normal goal context.
- `workflow` can show portable Yoke step orchestration while `native_workflow` remains provider-specific.
- `declared_subagents` and `skills` can show whether Yoke lowers them to provider files, SDK options, developer instructions, or provider-native roots.

Verification:

- `PYTHONPATH=src uv run pytest tests/test_capabilities.py`
- `PYTHONPATH=src uv run ruff check src/yoke/capabilities.py tests/test_capabilities.py`
