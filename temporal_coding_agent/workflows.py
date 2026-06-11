from datetime import timedelta

from temporalio import workflow

# These run inside the Temporal workflow sandbox. The agents/litellm SDKs and the
# plugin helpers aren't written for the deterministic sandbox, so we pass them
# through unchanged (the actual model + tool calls happen in activities, not here).
with workflow.unsafe.imports_passed_through():
    from agents import Agent, Runner
    from temporalio.contrib import openai_agents

    from activities import read_file, run_command, write_file


@workflow.defn
class CodingAgentWorkflow:
    @workflow.run
    async def run(self, task: str) -> str:
        agent = Agent(
            name="Coder",
            instructions=(
                "You are a coding assistant working in a sandboxed workspace. "
                "Use read_file, write_file, and run_command to complete the task. "
                "When you're done, briefly summarize what you did."
            ),
            # Just the model-name string; the plugin's LitellmProvider (set in
            # worker.py) resolves it via LiteLLM → Anthropic inside the model
            # activity. ANTHROPIC_API_KEY is read from the env there (worker loads .env).
            model="anthropic/claude-haiku-4-5",
            tools=[
                # activity_as_tool turns each Temporal activity into an agent tool.
                # The model calls them by name; Temporal runs them as activities.
                openai_agents.workflow.activity_as_tool(
                    read_file, start_to_close_timeout=timedelta(seconds=30)
                ),
                openai_agents.workflow.activity_as_tool(
                    write_file, start_to_close_timeout=timedelta(seconds=30)
                ),
                openai_agents.workflow.activity_as_tool(
                    run_command, start_to_close_timeout=timedelta(seconds=120)
                ),
            ],
        )

        # Runner.run IS the agent loop: reason -> call a tool -> observe -> repeat
        # until the model is done. The OpenAIAgentsPlugin makes every model call a
        # Temporal activity and activity_as_tool makes every tool call one too, so
        # the entire loop is checkpointed and survives a worker crash.
        result = await Runner.run(agent, input=task)
        return result.final_output
