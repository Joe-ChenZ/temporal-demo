import asyncio
import logging

from dotenv import load_dotenv
from temporalio.client import Client

load_dotenv()
from temporalio.worker import Worker

from activities import calculate, call_llm, get_weather
from workflows import AgentSessionWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="agent",
        workflows=[AgentSessionWorkflow],
        activities=[call_llm, calculate, get_weather],
    )

    print("Worker started, polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
