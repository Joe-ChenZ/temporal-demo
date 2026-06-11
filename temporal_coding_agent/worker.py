import asyncio
import logging
from datetime import timedelta

from dotenv import load_dotenv

# Load .env before anything imports litellm, so ANTHROPIC_API_KEY is present in
# the environment when the model activity makes the Claude call.
load_dotenv()

from temporalio.client import Client
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin
from temporalio.worker import Worker

from agents.extensions.models.litellm_provider import LitellmProvider

from activities import read_file, run_command, write_file
from workflows import CodingAgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    # The OpenAIAgentsPlugin wires the OpenAI Agents SDK into Temporal: it
    # registers the model-invocation activity and configures serialization so
    # Runner.run can execute durably inside the workflow.
    client = await Client.connect(
        "localhost:7233",
        plugins=[
            OpenAIAgentsPlugin(
                # Route model calls through LiteLLM (→ Anthropic). Without this the
                # plugin defaults to an OpenAI provider that builds an AsyncOpenAI
                # client and demands OPENAI_API_KEY at worker startup.
                model_provider=LitellmProvider(),
                model_params=ModelActivityParameters(
                    start_to_close_timeout=timedelta(seconds=120),
                ),
            ),
        ],
    )

    worker = Worker(
        client,
        task_queue="coding-agent",
        workflows=[CodingAgentWorkflow],
        activities=[read_file, write_file, run_command],
    )

    print("Coding-agent worker started, polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
