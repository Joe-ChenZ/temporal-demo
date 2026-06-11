# Temporal Python Demo Repo

Two self-contained demos showing **durable execution** with the [Temporal](https://temporal.io) Python SDK.

| Demo | What it shows |
|------|--------------|
| [`temporal_demo/`](temporal_demo/README.md) | Notification pipeline — sequential activities, automatic retries, crash recovery |
| [`temporal_agent/`](temporal_agent/README.md) | Durable AI agent — long-running session with a hand-rolled tool loop, signals, and queries |
| [`temporal_coding_agent/`](temporal_coding_agent/README.md) | Durable coding agent — OpenAI Agents SDK + `activity_as_tool`, Claude via LiteLLM (loop handled for you) |
| [`temporal_simple_agent/`](temporal_simple_agent/README.md) | Same coding agent, **hand-written loop** — plain Temporal + a LiteLLM call activity, no framework |

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Python 3.10+ | Required by `temporalio` |
| [uv](https://docs.astral.sh/uv/) | Package manager — `pip install uv` or see uv docs |
| Temporal CLI | For the dev server — see install note below |

### Install Temporal CLI (Windows)

Download the latest `temporal_cli_*_windows_amd64.zip` from [github.com/temporalio/cli/releases](https://github.com/temporalio/cli/releases), extract it, and place `temporal.exe` on your PATH.

### Start the dev server

```bash
temporal server start-dev
```

This runs an in-memory Temporal server on `localhost:7233` with the Web UI at `http://localhost:8233`. Keep this running in its own terminal for all demos.

---

## Setup

```bash
# From the repo root — installs all dependencies into .venv
uv sync
```

---

## Running a demo

See each subfolder's README for step-by-step instructions:

- **[temporal_demo/README.md](temporal_demo/README.md)** — notification pipeline with retries and crash recovery
- **[temporal_agent/README.md](temporal_agent/README.md)** — durable agent with a hand-rolled tool loop (Gemini)
- **[temporal_coding_agent/README.md](temporal_coding_agent/README.md)** — durable coding agent via the OpenAI Agents plugin (Claude/LiteLLM); needs `ANTHROPIC_API_KEY`
- **[temporal_simple_agent/README.md](temporal_simple_agent/README.md)** — the same coding agent with a hand-written loop on plain Temporal; needs `ANTHROPIC_API_KEY`

---

## Key Temporal concepts across both demos

| Concept | `temporal_demo` | `temporal_agent` |
|---------|----------------|-----------------|
| Activities | Email / FCM / Socket.IO sends | LLM call, calculate, get_weather |
| Retries | FCM fails 2× on purpose | LLM call retried on API error |
| Crash recovery | Kill worker, restart, pipeline resumes | Kill worker, restart, conversation resumes |
| Workflow type | Short-lived, completes after 3 steps | Long-running, waits indefinitely |
| Signals | — | `send_message` pushes user input in |
| Queries | — | `get_state` reads last response out |
