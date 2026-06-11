import asyncio
import logging

from dotenv import load_dotenv

# Load .env before litellm is imported, so ANTHROPIC_API_KEY is in the
# environment when the llm_call activity runs.
load_dotenv()

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from activities import llm_call, read_file, run_command, write_file
from workflows import SimpleCodingAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    # Plain Temporal — no plugin. The pydantic data converter lets typed models
    # (AssistantMessage) cross the activity boundary as real pydantic objects.
    client = await Client.connect(
        "localhost:7233",
        data_converter=pydantic_data_converter,
    )

    worker = Worker(
        client,
        task_queue="simple-agent",
        workflows=[SimpleCodingAgent],
        activities=[llm_call, read_file, write_file, run_command],
    )

    print("Simple-agent worker started, polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
