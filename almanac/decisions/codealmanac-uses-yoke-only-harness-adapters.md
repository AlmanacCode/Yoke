---
title: "codealmanac Uses Yoke-Only Harness Adapters"
summary: "codealmanac routes Claude and Codex execution through Yoke so the product owns wiki lifecycle work while Yoke owns provider surfaces."
topics: [decisions, integration, runtime]
sources:
  - id: boundary-note
    type: file
    path: docs/notes/0264-codealmanac-yoke-only-harness-boundary.md
  - id: package-note
    type: file
    path: docs/notes/0251-package-name-and-codealmanac-wiring.md
---

# codealmanac Uses Yoke-Only Harness Adapters

`codealmanac` uses Yoke as its only Claude and Codex harness adapter boundary.
The product keeps wiki lifecycle operations, job logging, changed-file
validation, and product records; Yoke owns provider-specific execution surfaces
for Claude and Codex [@boundary-note].

## Context

Earlier integration work had direct Claude and Codex adapter packages inside
`codealmanac`. The boundary note records that those packages created duplicate
implementations of provider behavior now owned by Yoke [@boundary-note].

Yoke also keeps a separate package identity: the Python distribution is
`almanac-yoke`, while the import package remains `yoke` [@package-note]. That
lets `codealmanac` depend on the publishable distribution while product code
continues to import the simple Python API [@package-note].

## Decision

`codealmanac` should call Yoke at the harness adapter boundary instead of
owning direct Claude or Codex orchestration. The default product composition
maps the Codex harness kind to `codex:app` and the Claude harness kind to
`claude:sdk` through Yoke-backed adapters [@boundary-note].

The hosted path stays layered as `usealmanac -> codealmanac lifecycle -> Yoke
-> Claude/Codex`, unless hosted product state later needs direct
provider-surface selection or Yoke capability reports [@boundary-note].

## Consequences

Future product work should add build, ingest, garden, validation, and lifecycle
behavior in `codealmanac`, but provider protocol changes belong in Yoke
[@boundary-note]. When `codealmanac` needs a different provider feature, the
adapter should select or configure a Yoke surface rather than recreating a
provider-specific client.

See [codealmanac Integration](../architecture/codealmanac-integration) for the
current integration architecture and [Provider Surfaces Are First-Class](provider-surfaces-first-class)
for the surface-planning decision behind the selected defaults.
