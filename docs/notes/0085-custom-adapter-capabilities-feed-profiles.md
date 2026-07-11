# Custom adapter capabilities feed profiles

Yoke supports registered adapters, not only built-in Claude and Codex surfaces. A custom adapter can declare its own `provider`, `surface`, and `capabilities`.

`profile_for()` now reads capabilities from registered adapters before falling back to the static built-in matrix. This matters because runtime methods call `Session.require(...)` and `Harness.require(...)` before dispatching. A custom registered surface that supports `streaming` or `structured_output` must be able to prove that through the same planning path as built-in surfaces.

This slice was exposed while adding session context managers: the fake test adapter could run and stream, but the planner treated its custom surface as unknown. The fix keeps ports/adapters honest: adapters own their capabilities, and profiles are the public view of that contract.

`Session` also supports async and sync context managers. `async with await harness.start() as session:` and `with session:` close through the existing adapter `close(session)` port.
