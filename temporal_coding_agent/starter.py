import asyncio
import sys
import uuid

from temporalio.client import Client
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from workflows import CodingAgentWorkflow

DEFAULT_TASK = (
    "Create hello.py that prints 'hello world', then run it and show the output."
)


async def main():
    task = " ".join(sys.argv[1:]) or DEFAULT_TASK

    # The client needs the plugin too, for compatible (de)serialization.
    client = await Client.connect(
        "localhost:7233",
        plugins=[OpenAIAgentsPlugin()],
    )

    print(f"Task: {task}")
    print("Web UI: http://localhost:8233\n")

    # execute_workflow blocks until the agent finishes and returns final_output.
    result = await client.execute_workflow(
        CodingAgentWorkflow.run,
        task,
        id=f"coding-agent-{uuid.uuid4().hex[:8]}",
        task_queue="coding-agent",
    )

    print("\n=== Agent result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
