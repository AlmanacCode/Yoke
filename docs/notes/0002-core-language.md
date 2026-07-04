# 0002: Core language and boundaries

Slice date: 2026-07-03

## Provider/library inspiration read

- Cosmic Python chapter 3: use simple abstractions to hide messy details.
- Cosmic Python chapter 4: service layers define use cases and sit between entrypoints and domain behavior.
- Cosmic Python project structure appendix: source packages can grow domain, adapters, services, and entrypoints as the shape earns them.

Prior Yoke research also read Eve, Claude Agent SDK, and Codex app-server. This slice did not re-implement provider behavior yet; it created the seam provider behavior must fit.

## Boundary pressure found

The public language needs to be small enough to feel obvious but rich enough to avoid pushing options onto `run()`.

Current split:

- `models.py`: provider-neutral nouns such as `Agent`, `Goal`, `Skill`, `Workflow`, `Harness`, `Session`, `Turn`, `Event`, and `Run`.
- `options.py`: per-call option placement, so `Agent` does not become a junk drawer.
- `ports.py`: provider behavior as a protocol. Claude and Codex adapters must implement this boundary later.
- `loader.py`: folder parity seed. It loads agent folders without provider compilation.

## API shape changed

Added:

- `Goal("...")` positional convenience.
- `Skill.from_path(...)` convenience.
- `Tools` and `Permissions` as explicit agent-level concepts.
- `RunOptions`, `SessionOptions`, `WorkflowOptions`, and `ProviderOptions`.
- `ProviderAdapter` protocol.
- `load(path)` folder loader.

## Why the current names feel right

The public model names are mostly single words:

- Agent
- Goal
- Skill
- Workflow
- Harness
- Session
- Turn
- Event
- Run

The less-pretty names are option names. They trade cleverness for placement clarity.

## What still feels muddy

- Whether `Harness` should be only a Pydantic value or the object with async methods.
- Whether `Workflow` should be a model, a callable wrapper, or both.
- Whether `ProviderOptions` should exist publicly or stay adapter-private.
- Whether folder workflow files should be YAML first or Python-first.

Next pressure test: build the Claude adapter slice and let the Claude Agent SDK force method placement.
