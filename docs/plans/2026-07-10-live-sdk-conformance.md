# Live SDK Conformance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Yoke's advertised Python SDK behavior match real Claude and Codex execution.

**Architecture:** Resolve user intent once at the provider boundary, preserve provider-native execution, and make unsupported or failed behavior explicit. Add bounded workflow execution and progress without rebuilding either provider's agent loop.

**Tech Stack:** Python 3.11+, Pydantic 2, Claude Agent SDK, Codex app-server/Python SDK, pytest.

---

### Task 1: Strict structured output

- Add regression tests for nested Pydantic schemas.
- Normalize object schemas recursively for Codex strict JSON Schema.
- Preserve typed Pydantic results when the caller supplied a model class.
- Verify focused tests, then live Codex structured output.

### Task 2: Model truth across Codex surfaces

- Add failing tests for run/session model override forwarding.
- Parse typed Codex SDK model-list responses from `data`.
- Resolve the model once and carry requested model metadata on normalized runs.
- Make SDK readiness exercise the underlying runtime rather than import alone.
- Verify focused tests, then live model listing and override behavior.

### Task 3: Claude permissions and event fidelity

- Reproduce write + non-interactive approval lowering.
- Map Yoke permissions to a Claude mode that actually permits the declared work.
- Ensure denied/incomplete filesystem work is not reported as successful where provider evidence identifies failure.
- Deduplicate final streamed text and preserve typed structured output.
- Verify focused tests, then live file creation, native subagent use, and streaming.

### Task 4: Bounded, observable workflows

- Add workflow/step timeout options.
- Return typed partial failure with the active/failed step.
- Add a workflow event stream or callback carrying step lifecycle events.
- Verify DAG ordering, concurrency, cancellation, and partial results.
- Live-test a multi-step workflow that creates and reviews files.

### Task 5: SDK discovery and authentication ergonomics

- Add concise authentication status/method metadata without storing secrets.
- Distinguish installed, authenticated, compatible, and live-tested readiness.
- Add one concise discovery path while retaining explicit `Harness` construction.
- Document a complete copy-pasteable folder and Python example.
- Run full tests, Ruff, build, all live labs, and final subagent review.
