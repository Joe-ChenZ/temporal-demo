import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from activities import send_email, send_fcm, send_socketio
from workflows import NotificationWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="notifications",
        workflows=[NotificationWorkflow],
        activities=[send_email, send_fcm, send_socketio],
    )

    print("Worker started, polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
