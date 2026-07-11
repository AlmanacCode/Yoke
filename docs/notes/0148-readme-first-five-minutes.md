# README first-run path is shorter

Date: 2026-07-04

The README now has a "First five minutes" section before the longer small-path explanation.

The new spine is:

1. define an `Agent`;
2. create a `Harness` with an explicit provider surface alias;
3. call `status()` to inspect readiness and the selected report key;
4. call `run(...)`;
5. choose optional paths: `report()`, `Agent.save(...)`, `bundle(...).write(...)`, or `workflow(...)`.

This keeps the public story aligned with Yoke's core model: folder source, provider-native bundle artifacts, and surface reports are separate but connected. It also makes the first snippet copy-pasteable by including imports.

A duplicated "Methods with obvious requirements..." sentence was removed while editing the quickstart section.
