# 0094 - App-server interrupted turns are cancelled

Codex app-server reports interrupted work as `turn/completed` with
`turn.status == "interrupted"`.

Yoke now maps that provider status to:

```python
RunStatus.CANCELLED
```

instead of treating every non-error `turn/completed` event as success.

This keeps interruption as a lifecycle operation, not an error. A failed turn
still maps to `RunStatus.FAILED` when the app-server event carries an error.

The event stream still yields a terminal `done` event with message
`codex interrupted`; a future slice can decide whether Yoke should add a
first-class `cancelled` event kind.
