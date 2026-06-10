# temporal_demo — Notification Pipeline

Demonstrates **durable execution** for a simple three-step notification pipeline: email → FCM → Socket.IO. FCM is rigged to fail the first two attempts so you can watch Temporal auto-retry in the Web UI. Killing the worker mid-flight and restarting it shows crash recovery — completed steps are never re-run.

---

## Files

```
temporal_demo/
├── activities.py   # send_email, send_fcm (fails attempts 1 & 2), send_socketio
├── workflows.py    # NotificationWorkflow — three activities run sequentially
├── worker.py       # registers workflow + activities on task queue "notifications"
└── starter.py      # starts one workflow run and exits immediately
```

---

## Run

> Assumes `temporal server start-dev` is already running and `uv sync` has been run from the repo root.

**Terminal 1 — worker:**

```bash
uv run python temporal_demo/worker.py
```

**Terminal 2 — trigger a workflow:**

```bash
uv run python temporal_demo/starter.py            # default: user-123
uv run python temporal_demo/starter.py alice      # custom user ID
```

Watch Terminal 1 for activity logs. Open **http://localhost:8233** and click into the workflow to see the event history.

Expected output:

```
sending email to user-123
email sent to user-123
sending FCM to user-123 (attempt 1)   ← exception raised, Temporal retries
sending FCM to user-123 (attempt 2)   ← exception raised, Temporal retries
sending FCM to user-123 (attempt 3)   ← succeeds
FCM sent to user-123
sending SIO push to user-123
SIO sent to user-123
```

---

## Crash-recovery demo

1. Start the worker (Terminal 1).
2. Trigger a workflow with a fresh ID: `uv run python temporal_demo/starter.py demo-crash`
3. The moment you see `email sent to demo-crash`, kill the worker with **Ctrl+C**.
4. Check **http://localhost:8233** — the workflow is `Running`, and `send_email` is already `Completed` in the history.
5. Restart the worker: `uv run python temporal_demo/worker.py`
6. Temporal replays from `send_fcm`. **No second email is sent.**

---

## Key concepts

| Concept | Where |
|---------|-------|
| Sequential activities | `workflows.py` — three chained `execute_activity` calls |
| Automatic retries | `send_fcm` — raises on attempts 1 & 2, succeeds on 3 |
| Retry policy | `RetryPolicy(maximum_attempts=5)` per activity |
| Fire-and-forget start | `starter.py` uses `start_workflow`, not `execute_workflow` |
| Crash recovery | Kill + restart worker — pipeline resumes from last completed step |
