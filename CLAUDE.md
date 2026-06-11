# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Four self-contained demos of **durable execution** with the [Temporal](https://temporal.io) Python SDK:

- `temporal_demo/` — a three-step notification pipeline (email → FCM → Socket.IO) showing sequential activities, automatic retries, and crash recovery.
- `temporal_agent/` — a long-running Gemini chat agent wrapped in a Temporal workflow, showing signals, queries, and a **hand-rolled** agentic tool loop. The loop, history, and tool dispatch are all hand-written in the workflow.
- `temporal_coding_agent/` — a durable **coding** agent (read/write files, run commands) built the *framework* way: the OpenAI Agents SDK runs **inside** the workflow via `temporalio.contrib.openai_agents`, with `Runner.run` as the loop, `activity_as_tool` exposing each tool, and Claude (`claude-haiku-4-5`) reached through LiteLLM. The loop is handled for you.
- `temporal_simple_agent/` — the **same** coding agent (same tools, same model) with a **hand-written** loop on plain Temporal: an `llm_call` activity wraps `litellm.acompletion` (`num_retries=0` so Temporal owns retries), and `workflows.py` contains the actual agent loop (~30 lines) — ask the model, run requested tools as activities, append results, repeat. Hand-written `TOOLS` schemas and an explicit `if name == ...` dispatch. This is the "see how an agent works" version; read `workflows.py` top to bottom and you've seen the whole agent. Typed with pydantic: `llm_call` returns a `models.AssistantMessage` (validated from LiteLLM's reply), and **both** the worker and starter clients use `temporalio.contrib.pydantic.pydantic_data_converter` so the typed object survives the activity boundary — set it on both or (de)serialization won't match.

Both are illustrative demos, not production code. Activities `asyncio.sleep` to simulate latency, and `send_fcm` deliberately raises on its first two attempts so the retry behavior is visible in the Web UI.

## Running things

A Temporal dev server must be running for anything to work (provides the server on `localhost:7233` and Web UI on `http://localhost:8233`):

```bash
temporal server start-dev
```

Dependencies are managed with [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv sync                                      # install deps into .venv
uv run python temporal_demo/worker.py        # run a worker (Terminal 1)
uv run python temporal_demo/starter.py [id]  # trigger a workflow (Terminal 2)
```

Same pattern for `temporal_agent/` (the worker additionally needs `GOOGLE_API_KEY`, see below). There is no build step, linter, or test suite — verification is done by running a worker + starter and watching the worker logs and the Web UI event history.

## Architecture: the file quartet

Each demo is a directory of four files following the standard Temporal SDK layout. **The same role-based structure repeats in both demos**, so understanding one transfers to the other:

| File | Role |
|------|------|
| `activities.py` | `@activity.defn` functions — the side-effecting work (network calls, LLM calls, tool execution). May be non-deterministic. |
| `workflows.py` | `@workflow.defn` class — deterministic orchestration that calls activities via `workflow.execute_activity`. Must never do I/O directly. |
| `worker.py` | Connects to `localhost:7233`, registers the workflow + activities on a **task queue**, and polls. |
| `starter.py` | Client that kicks off / connects to a workflow run. |

Task queue names are the contract between starter, worker, and workflow: `"notifications"` for the demo, `"agent"` for the agent. A starter and worker only find each other if their task queues match.

### Critical convention: flat imports + run-from-script-dir

Both modules import siblings *without a package prefix* (`from activities import ...`, `from workflows import ...`). This only resolves because Python puts the script's own directory on `sys.path` when you run `python <dir>/worker.py`. Consequences:

- Always launch via the full path from the repo root (`uv run python temporal_demo/worker.py`), never `cd` into the subdir and run, and don't convert these into a package with relative imports without updating every entry point.
- In `workflows.py`, activity imports are wrapped in `with workflow.unsafe.imports_passed_through():` — required by Temporal's sandbox so the workflow code can reference activity functions without the sandbox re-importing (and re-validating determinism of) their module.

## The durability model (why the code is shaped this way)

Temporal replays workflow code from an event history to recover state after a crash. This drives two hard rules that both `workflows.py` files follow:

1. **Workflows must be deterministic.** No direct I/O, no `time`/`random`, no network. Anything non-deterministic goes in an activity. Completed activities are recorded in history and never re-run on replay — that is what makes "kill the worker, restart it, work resumes without repeating steps" work (and why an LLM call is never re-billed after a crash).
2. **Retries are declared, not coded.** Each `execute_activity` call takes a `RetryPolicy` and a `start_to_close_timeout`. The notification demo uses `maximum_attempts=5`; the agent uses `maximum_attempts=3`. There are no try/retry loops in application code.

### `temporal_agent` specifics

`AgentSessionWorkflow` is a **long-running** workflow (the demo workflow completes after three steps; this one loops forever):

- It keeps `self._history` (the full conversation including tool calls) as in-memory state, rebuilt deterministically on replay from the event log.
- `@workflow.signal send_message` pushes user input in; the run loop blocks on `workflow.wait_condition(lambda: self._pending_message is not None)`.
- `@workflow.query get_state` reads `last_response` / `response_count` / `is_processing` out without mutating state. The CLI in `starter.py` signals a message, then **polls** `get_state` every 0.3s until `response_count` increments — this is how it detects a completed response.
- The inner agentic loop calls `call_llm`, and if the model returned tool calls, dispatches each as its own activity (`calculate` or `get_weather`), appends results to history, and loops again until the model stops requesting tools.
- `starter.py` reconnects to an existing run by workflow ID (`agent-<session_id>`) if it's still `RUNNING`, otherwise starts a new one — so Ctrl+C on the CLI leaves the session alive in Temporal.

### `temporal_coding_agent` specifics

This one does **not** hand-roll the loop — that's the whole point. It uses the OpenAI Agents SDK integration shipped in `temporalio.contrib.openai_agents`:

- `workflows.py` builds an `Agent` and calls `Runner.run(agent, task)` — that *is* the agent loop, running durably inside the workflow. There is no `while`-loop, no manual history, no `if name == ...` dispatch.
- The `OpenAIAgentsPlugin` is passed to `Client.connect(...)` on **both** `worker.py` and `starter.py`. On the worker it auto-registers the model-invocation activity and configures serialization; both sides need it or (de)serialization mismatches.
- Tools are plain `@activity.defn` functions wrapped with `openai_agents.workflow.activity_as_tool(fn, start_to_close_timeout=...)`. Adding a tool = write an activity, register it on the `Worker`, add one `activity_as_tool` line. No workflow surgery.
- The model is Claude (`claude-haiku-4-5`, the cheapest Anthropic model) via `LitellmModel("anthropic/claude-haiku-4-5")`. LiteLLM reads `ANTHROPIC_API_KEY` from the environment **when the model activity runs**, so the workflow stays deterministic — `worker.py` calls `load_dotenv()` before litellm is imported; the workflow never reads env.
- `workflows.py` wraps the `agents` / `litellm` / contrib / activity imports in `with workflow.unsafe.imports_passed_through():` so they bypass the deterministic sandbox (the real model + tool calls happen in activities, not the workflow body).
- Tools are scoped to `temporal_coding_agent/workspace/` (gitignored). `run_command` executes real shell commands on the host — fine for a local demo, not for untrusted input.

## LLM configuration note

Two different LLM setups coexist:

- `temporal_agent/activities.py` uses **Google Gemini** directly (`google-genai`, `gemini-2.0-flash`, `GOOGLE_API_KEY`). The tool-declaration format (`types.FunctionDeclaration`) and message-history shape (`{"role": ..., "parts": [...]}`) are Gemini-specific.
- `temporal_coding_agent/` uses **Claude** (`claude-haiku-4-5`) through LiteLLM + the OpenAI Agents plugin and reads `ANTHROPIC_API_KEY`.

Both load the repo-root `.env` via `load_dotenv()` in their `worker.py` before the LLM client is imported. Set both keys in `.env` (see `.env.example`). Dependencies for the coding agent come from the `temporalio[openai-agents,opentelemetry]` extra plus `litellm` (the contrib imports `opentelemetry` unconditionally, so the `opentelemetry` extra is required even though no OTEL export is configured).
