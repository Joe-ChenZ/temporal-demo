# Temporal Notification Pipeline Demo

Demonstrates **durable execution** with the Temporal Python SDK: sequential activities, automatic retries (FCM fails the first two attempts on purpose), and crash recovery without re-running completed steps.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| uv | any recent version |
| Temporal dev server | running on `localhost:7233` |
| Temporal Web UI | available at `http://localhost:8233` |

Start the dev server if it is not already running:

```bash
temporal server start-dev
```

---

## Setup

```bash
# Install dependencies and create .venv in one step
uv sync

# Run any script through uv so it uses the managed venv automatically
uv run python temporal_demo/worker.py
```

No manual venv activation needed — `uv run` handles it.

---

## Running the demo

Open **two terminals** side by side, both with the venv activated and both `cd`'d into `temporal_demo/`.

### Terminal 1 — Start the worker

```bash
uv run python temporal_demo/worker.py
```

You should see:

```
Worker started, polling for tasks...
```

### Terminal 2 — Start a workflow

```bash
uv run python temporal_demo/starter.py          # uses default user-123
# or
uv run python temporal_demo/starter.py alice    # uses user-alice
```

You should see:

```
Workflow started: notification-user-123 — check http://localhost:8233
```

Switch back to **Terminal 1** and watch the activity logs appear in sequence:

```
sending email to user-123
email sent to user-123
sending FCM to user-123 (attempt 1)   ← raises Exception, Temporal retries
sending FCM to user-123 (attempt 2)   ← raises Exception, Temporal retries
sending FCM to user-123 (attempt 3)   ← succeeds
FCM sent to user-123
sending SIO push to user-123
SIO sent to user-123
```

Open **http://localhost:8233** to see the workflow in the Web UI. Click into it and navigate to the **History** tab to watch each activity event (scheduled → started → completed / failed → retried).

---

## Crash-recovery demo

This shows the core Temporal guarantee: **a completed activity is never re-run, even if the worker crashes.**

### Step-by-step

1. Start the worker in Terminal 1:

   ```bash
   uv run python temporal_demo/worker.py
   ```

2. Start a fresh workflow with a new user ID so there is no conflict:

   ```bash
   uv run python temporal_demo/starter.py demo-crash
   ```

3. Watch Terminal 1. The moment you see `email sent to demo-crash` (i.e., the email activity has completed), **kill the worker** with `Ctrl+C`.

4. Open the Web UI at `http://localhost:8233`. Find `notification-demo-crash`. Its status will be `Running` — Temporal is waiting for the next activity heartbeat. You can see in the history that `send_email` is already `Completed`.

5. Restart the worker in Terminal 1:

   ```bash
   uv run python temporal_demo/worker.py
   ```

6. The worker picks up exactly where it left off. You will see:

   ```
   sending FCM to demo-crash (attempt 1)
   sending FCM to demo-crash (attempt 2)
   sending FCM to demo-crash (attempt 3)
   FCM sent to demo-crash
   sending SIO push to demo-crash
   SIO sent to demo-crash
   ```

   **No second email is sent.** The workflow resumed from `send_fcm`, skipping the already-completed `send_email`.

7. The workflow moves to `Completed` in the Web UI. Clicking the **Result** tab shows:

   ```json
   {
     "email": "email:demo-crash",
     "fcm": "fcm:demo-crash",
     "socketio": "sio:demo-crash"
   }
   ```

---

## Project layout

```
temporal_demo/
├── activities.py   # send_email, send_fcm (fails 2×), send_socketio
├── workflows.py    # NotificationWorkflow — runs activities sequentially
├── worker.py       # connects to Temporal, registers workflow + activities
└── starter.py      # fires off one workflow run and exits immediately
```

## Key concepts shown

| Concept | Where |
|---------|-------|
| Durable execution / crash recovery | Kill worker mid-flight, restart it |
| Automatic retries with backoff | `send_fcm` — fails attempts 1 & 2, succeeds on attempt 3 |
| Sequential activity chaining | `workflows.py` — three `await execute_activity` calls |
| `start_workflow` (fire-and-forget) | `starter.py` — returns immediately, worker runs async |
| Retry policy configuration | `RetryPolicy(maximum_attempts=5)` per activity |
