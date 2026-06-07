import asyncio
import sys

from temporalio.client import Client

from workflows import NotificationWorkflow


async def main():
    user_id = sys.argv[1] if len(sys.argv) > 1 else "user-123"
    workflow_id = f"notification-{user_id}"

    client = await Client.connect("localhost:7233")

    await client.start_workflow(
        NotificationWorkflow.run,
        user_id,
        id=workflow_id,
        task_queue="notifications",
    )

    print(f"Workflow started: {workflow_id} — check http://localhost:8233")


if __name__ == "__main__":
    asyncio.run(main())
