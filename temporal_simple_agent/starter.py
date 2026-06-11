import asyncio
import sys
import uuid

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from workflows import SimpleCodingAgent

DEFAULT_TASK = (
    "Create hello.py that prints 'hello world', then run it and show the output."
)


async def main():
    task = " ".join(sys.argv[1:]) or DEFAULT_TASK

    # Must match the worker's data converter so payloads (de)serialize the same.
    client = await Client.connect(
        "localhost:7233",
        data_converter=pydantic_data_converter,
    )

    print(f"Task: {task}")
    print("Web UI: http://localhost:8233\n")

    result = await client.execute_workflow(
        SimpleCodingAgent.run,
        task,
        id=f"simple-agent-{uuid.uuid4().hex[:8]}",
        task_queue="simple-agent",
    )

    print("\n=== Agent result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
