# Codex SDK interrupt is stream-handle scoped

The Codex Python SDK exposes interruption through `TurnHandle.interrupt()` and `AsyncTurnHandle.interrupt()`. Those handles are returned by `Thread.turn()` and `AsyncThread.turn()`.

Yoke therefore wires `Session.interrupt()` for active streamed SDK turns. The adapter stores the active turn handle while `stream()` is consuming provider events and clears it when the stream exits.

Yoke does not claim that opaque `Thread.run()` calls can be interrupted after they start. The SDK's convenience `run()` method creates and consumes a turn internally, so Yoke has no stable public handle to interrupt from another call.

Implication: callers that need control should use sessions plus streaming. One-shot convenience remains simple, while app-server and SDK streaming surfaces expose stronger live-control affordances.
