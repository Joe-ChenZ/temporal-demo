# Notes: making the agent conversational (long-running)

`temporal_simple_agent` runs one prompt and exits (`run(task) -> str`). To make it a
multi-turn conversational agent, turn the one-shot workflow into a long-running session.
Same shape as `temporal_agent/`, but with this demo's clean typed LiteLLM loop. Four
changes:

1. **Long-running workflow.** `run(session_id)` loops forever, holding `self._messages` as
   workflow state (seed the system prompt once). The durable workflow state *is* the
   conversation memory for as long as the session lives.
2. **Signal `send_message(text)`** — pushes each new user prompt into the *same* running
   workflow (you can't return-and-restart; that resets memory). The run loop blocks on
   `workflow.wait_condition(...)` until a message arrives.
3. **Query `get_state()`** — returns the latest assistant response + a response counter +
   an `is_processing` flag, without mutating state, so the client knows when a reply is
   ready.
4. **Interactive client** — connect to a *stable* workflow id (e.g. `chat-<session>`),
   reconnect if it's still `RUNNING`, then loop: read a line → signal it → poll
   `get_state` until the counter increments → print. (Signals can't return values, so the
   CLI polls the query — exactly what `temporal_agent/starter.py` does.)

## The one tricky part: `continue_as_new`

A forever-looping workflow accumulates event history without bound (every signal,
activity, and result is logged). For a genuinely long conversation, periodically call
`workflow.continue_as_new(session_id, self._messages, self._response_count)` to start a
fresh run carrying the conversation forward — bounding the history. Notes:

- Only continue when no user message is pending (don't drop buffered signals).
- Carry **both** `messages` *and* the response counter across, so the polling CLI's
  monotonic counter doesn't reset.
- This is the durable-execution analog of context **compaction** — and the thing
  `temporal_agent` is missing (it loops forever without it).

## Reference

- `temporal_agent/` — the existing long-running signal/query agent (template for the
  shape; hand-rolled/Gemini, and missing `continue_as_new`).
- `temporal_simple_agent/workflows.py` — the current one-shot loop to evolve.
