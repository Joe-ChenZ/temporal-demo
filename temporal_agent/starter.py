import asyncio
import sys

from temporalio.client import Client, WorkflowExecutionStatus

from workflows import AgentSessionWorkflow

POLL_INTERVAL = 0.3  # seconds between query polls


async def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    workflow_id = f"agent-{session_id}"

    client = await Client.connect("localhost:7233")

    handle = client.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
        if desc.status == WorkflowExecutionStatus.RUNNING:
            print(f"Reconnected to existing session (id: {workflow_id})")
        else:
            handle = await client.start_workflow(
                AgentSessionWorkflow.run,
                session_id,
                id=workflow_id,
                task_queue="agent",
            )
            print(f"Agent session started (id: {workflow_id})")
    except Exception:
        handle = await client.start_workflow(
            AgentSessionWorkflow.run,
            session_id,
            id=workflow_id,
            task_queue="agent",
        )
        print(f"Agent session started (id: {workflow_id})")
    print(f"Web UI: http://localhost:8233")
    print(f"Tools available: calculate, get_weather")
    print(f"Type your message and press Enter. Ctrl+C to exit (session stays alive in Temporal).\n")

    # Grab current response_count so we can detect when a new response arrives
    state = await handle.query(AgentSessionWorkflow.get_state)
    seen_count = state["response_count"]

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting CLI — session remains running in Temporal.")
            break

        if not user_input:
            continue

        await handle.signal(AgentSessionWorkflow.send_message, user_input)

        # Poll until response_count increases
        print("Agent: ", end="", flush=True)
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            state = await handle.query(AgentSessionWorkflow.get_state)
            if state["response_count"] > seen_count:
                seen_count = state["response_count"]
                print(state["last_response"])
                break


if __name__ == "__main__":
    asyncio.run(main())
