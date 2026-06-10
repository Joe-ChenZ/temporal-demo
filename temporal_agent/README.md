# temporal_agent — Durable AI Agent Session

Wraps a Claude-powered multi-turn chat agent in a long-running Temporal workflow. The full conversation history — including tool calls — lives in Temporal's event log. If the worker crashes mid-response, the session resumes exactly where it left off with no lost messages and no repeated LLM calls.

---

## Files

```
temporal_agent/
├── activities.py   # call_llm (Claude API), calculate, get_weather
├── workflows.py    # AgentSessionWorkflow — signal/query + agentic tool loop
├── worker.py       # registers workflow + activities on task queue "agent"
└── starter.py      # CLI interactive loop — signals messages in, queries responses out
```

---

## Setup

Copy `.env.example` from the repo root and fill in your key:

```bash
cp ../.env.example ../.env
# then edit .env and set GOOGLE_API_KEY=AIza...
```

Get a free API key at **aistudio.google.com** → Get API key. The worker loads `.env` automatically on startup. The starter does not need the key.

---

## Run

> Assumes `temporal server start-dev` is already running and `uv sync` has been run from the repo root.

**Terminal 1 — worker** (with API key set):

```bash
uv run python temporal_agent/worker.py
```

**Terminal 2 — start a chat session:**

```bash
uv run python temporal_agent/starter.py            # session id: default
uv run python temporal_agent/starter.py my-session # custom session id
```

Type messages at the `You:` prompt. Press **Ctrl+C** to exit the CLI — the workflow keeps running in Temporal and can be reconnected to.

---

## Try these prompts

| Prompt | What you'll see in the Web UI |
|--------|------------------------------|
| `hello, what can you do?` | Single `call_llm` activity |
| `what is 144 * 37?` | `call_llm` → `calculate` activity → `call_llm` again |
| `what's the weather in Tokyo?` | `call_llm` → `get_weather` activity (2s) → `call_llm` again |
| `what is (12^3 + 50) / 7?` | Tool use with a more complex expression |

Open **http://localhost:8233**, click the workflow, and watch the History tab update in real time.

---

## Crash-recovery demo

1. Start the worker (Terminal 1) and the CLI (Terminal 2).
2. Ask something that triggers a tool: `"what's the weather in Tokyo?"`
3. While the `get_weather` activity is sleeping (2 seconds), kill the worker with **Ctrl+C**.
4. Check the Web UI — the workflow is `Running`, and the completed `call_llm` step is already in the history.
5. Restart the worker: `uv run python temporal_agent/worker.py`
6. The workflow replays and completes from `get_weather` onward. No LLM call is re-billed.

---

## How it works

| Concept | Role |
|---------|------|
| Long-running workflow | The session loop runs indefinitely, waiting between messages |
| Signal `send_message` | Pushes user input into the running workflow from the CLI |
| Query `get_state` | CLI polls this to detect when a new response is ready |
| `call_llm` activity | Each Claude API call is a retryable, durable activity |
| `calculate` / `get_weather` | Tool calls are also activities — visible in Web UI, crash-safe |
| Event history | Full conversation + tool calls stored in Temporal's log |
