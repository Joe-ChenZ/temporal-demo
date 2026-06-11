# temporal_coding_agent — Durable Claude Coding Agent

A tiny coding agent (read files, write files, run commands) that's **durable by
construction**: the agent loop runs *inside* a Temporal workflow, every Claude call is a
Temporal activity, and every tool call is a Temporal activity. Crash the worker mid-task,
restart it, and the agent resumes — no re-billed model calls, no re-run commands.

Unlike `temporal_agent/`, **none of the loop is hand-written**. It's built on Temporal's
[OpenAI Agents SDK integration](https://github.com/temporalio/samples-python/tree/main/openai_agents)
(`temporalio.contrib.openai_agents`), with Claude reached through LiteLLM.

---

## Files

```
temporal_coding_agent/
├── activities.py   # read_file, write_file, run_command — each a Temporal activity
├── workflows.py    # CodingAgentWorkflow — Agent + Runner.run, tools via activity_as_tool
├── worker.py       # registers the workflow + activities, installs OpenAIAgentsPlugin
├── starter.py      # kicks off one task and prints the result
└── workspace/      # created on first run; the agent's sandboxed working dir
```

---

## How it works

```
Runner.run(agent, task)          <- the agent loop, running inside the workflow
        │
        ├─ model call ──────────▶ Temporal activity  (Claude via LiteLLM)
        │       │
        │   tool call?
        │       ▼
        ├─ read_file / write_file / run_command ──▶ Temporal activity (activity_as_tool)
        │       │
        │   result fed back to the model
        │       ▼
        └─ repeat until the model is done ──▶ final_output
```

- **`OpenAIAgentsPlugin`** (in `worker.py`) makes every model invocation a Temporal
  activity automatically.
- **`activity_as_tool`** (in `workflows.py`) wraps each `@activity.defn` so the model can
  call it as a tool — and that call, too, is a durable activity.
- **`Runner.run`** is the whole reason → act → observe loop. You don't write it.

Because each step is an activity recorded in Temporal's event log, a worker crash replays
completed steps rather than re-running them. That's the payoff — visible in the Web UI.

---

## Setup

> Assumes `temporal server start-dev` is running and `uv sync` has been run from the repo
> root (it installs `openai-agents` and `litellm`).

Add your Anthropic key to the repo-root `.env`:

```bash
cp ../.env.example ../.env   # if you haven't already
# then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

LiteLLM reads `ANTHROPIC_API_KEY` from the environment inside the model activity; the
worker loads `.env` on startup. The model is `claude-haiku-4-5` (cheapest Anthropic model);
change the `LitellmModel(...)` string in `workflows.py` to use a bigger one.

> **Note — why you only need `ANTHROPIC_API_KEY`, not `OPENAI_API_KEY`:** the plugin's model
> activity defaults to an OpenAI provider that builds an `AsyncOpenAI` client at worker
> startup and demands `OPENAI_API_KEY`. We pass `model_provider=LitellmProvider()` so calls
> route through LiteLLM → Anthropic instead (and the agent's `model` is a plain name string
> the provider resolves, **not** a `LitellmModel` instance — the plugin only forwards the
> model name). The SDK also traces to OpenAI's platform by default, but with no
> `OPENAI_API_KEY` it just logs a harmless `skipping trace export` warning and continues —
> no action needed (call `agents.set_tracing_disabled(True)` if you want to silence it).

---

## Run

**Terminal 1 — worker** (needs the API key):

```bash
uv run python temporal_coding_agent/worker.py
```

**Terminal 2 — give it a task:**

```bash
uv run python temporal_coding_agent/starter.py            # default: write + run hello.py
uv run python temporal_coding_agent/starter.py "Write fib.py with a fib(n) function, run fib(10), print the result"
```

Files land in `temporal_coding_agent/workspace/`. Open **http://localhost:8233** and watch
the workflow history: you'll see the model calls and each `read_file` / `write_file` /
`run_command` as separate activities.

---

## Try these tasks

| Task | What you'll see |
|------|-----------------|
| `Write hello.py that prints hello world and run it` | `write_file` → `run_command` |
| `Write fizzbuzz.py for 1..20, run it, then fix any bug and re-run` | multiple write/run rounds |
| `Read hello.py and explain what it does` | `read_file` → final text |

---

## Crash-recovery demo

1. Start the worker (Terminal 1) and a multi-step task (Terminal 2).
2. While a `run_command` or model call is in flight, kill the worker with **Ctrl+C**.
3. In the Web UI the workflow is still `Running`; completed activities are in the history.
4. Restart the worker: `uv run python temporal_coding_agent/worker.py`.
5. The agent resumes from the next step — completed Claude calls and commands are **not**
   repeated.

---

## vs `temporal_agent`

| | `temporal_agent` | `temporal_coding_agent` |
|---|---|---|
| Agent loop | hand-written `while True` in the workflow | `Runner.run` (OpenAI Agents SDK) |
| History/messages | hand-built provider-shaped dicts | managed by the SDK |
| Tool dispatch | manual `if name == ...` in the workflow | `activity_as_tool`, model-driven |
| Adding a tool | edit the workflow's dispatch logic | add an `@activity.defn` + one `activity_as_tool` line |
| Model | Gemini, called directly in one activity | Claude via LiteLLM, called by the plugin |
