# README plan explainability gap

2026-07-04

## Finding

The README is behind the public planning API after `Plan.reports`.

The README currently teaches `harness.plan(...)` as non-executing surface
selection:

```python
plan = harness.plan(RunOptions(output_schema=Summary), channel=Channel.APP_SERVER)
print(plan.ok, plan.surface, plan.missing)
```

It also teaches capability reports separately through `harness.report()`,
`report_for(...)`, `matrix_for(...)`, and `status()` sections.

The missing bridge is plan-level explainability. The API now lets callers ask
"for this exact requested run shape, how will each requested feature be lowered
on the selected surface?" before execution:

```python
plan = harness.plan(RunOptions(output_schema=Summary))

for row in plan.reports:
    print(row.feature, row.support, row.lowering)

print(plan.report("structured_output"))
```

That is different from the broader capability-report APIs. `plan.reports` is
filtered to the features that participated in this plan and attached to the
surface selected by this plan.

## Why it matters

Yoke's README promise is "honest provider behavior underneath." For planning,
honesty now includes the lowering explanation, not just `ok`, `surface`, and
`missing`.

Without a README example, users may think they must call `harness.report()` or
`matrix_for(...)` and manually join the capability table back to a plan. The
code already does that join for them.

## API/doc alignment

Current public API:

- `Plan.ok` answers whether the selected fit satisfies the required features.
- `Plan.provider`, `Plan.surface`, and `Plan.missing` expose direct diagnostics.
- `Plan.reports` returns `FeatureReport` rows for the requested features on the
  selected surface.
- `Plan.report(feature)` returns one requested feature row or `None`.
- `FeatureReport.lowering`, `recipes`, and `evidence` explain the provider
  mapping.

Current README coverage:

- Covered: non-executing planning.
- Covered: direct `plan.ok`, `plan.surface`, and `plan.missing`.
- Covered elsewhere: feature reports have `lowering`, `recipes`, and
  `evidence`.
- Missing: `plan.reports` / `plan.report(feature)` as the short path from a
  planned run to its lowering explanation.

## Recommended README change

Add a small paragraph after the existing `plan(...)` snippet:

```python
plan = harness.plan(RunOptions(output_schema=Summary), channel=Channel.APP_SERVER)

for row in plan.reports:
    print(row.feature, row.support, row.lowering)

print(plan.report(Feature.STRUCTURED_OUTPUT))
```

Suggested prose:

> Plans also carry feature reports for the selected surface. Use
> `plan.reports` when you want to explain how this exact run shape will lower
> requested features before execution. Use `plan.report(feature)` when you only
> need one row. Broader APIs such as `harness.report()`, `report_for(...)`, and
> `matrix_for(...)` remain the right tools for surface-wide capability audits.

## Scope

No code change is needed for this gap. The source and tests already expose the
plan-level explainability API. This is a README/API-docs alignment issue.
