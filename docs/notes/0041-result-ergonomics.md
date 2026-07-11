# Result ergonomics

Date: 2026-07-04

Yoke is data-first: runs and workflows return `status` and `failure` instead of raising for provider-declared failures.

Callers now also get small convenience helpers:

```python
result.ok
result.raise_for_status()
```

`Run` and `WorkflowRun` both support these helpers.

The rule:

- Provider-declared failure returns data.
- `raise_for_status()` is caller opt-in.
- Infrastructure errors can still raise directly.

This keeps embedding apps like CodeAlmanac in control of how failures enter their own job ledgers, while making simple scripts pleasant:

```python
result = await harness.run("Do the thing.")
result.raise_for_status()
print(result.output)
```
