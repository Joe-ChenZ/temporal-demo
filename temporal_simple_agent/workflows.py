import json
from datetime import timedelta

from temporalio import workflow

# The activities import litellm, which isn't written for the workflow sandbox.
# Pass the imports through unchanged — the actual calls happen in activities.
with workflow.unsafe.imports_passed_through():
    from activities import llm_call, read_file, run_command, write_file
    from models import AssistantMessage

MODEL = "anthropic/claude-haiku-4-5"

SYSTEM = (
    "You are a coding assistant working in a sandboxed workspace. "
    "Use the tools to read, write, and run files. "
    "When you're done, briefly summarize what you did."
)

# Tool schemas in OpenAI function-calling shape, so the model knows what it can
# call. (This is the boilerplate the plugin's activity_as_tool generated for us;
# here we write it by hand.)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a text file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the workspace and return its output.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

_LLM_TIMEOUT = timedelta(seconds=60)
_TOOL_TIMEOUT = timedelta(seconds=120)


@workflow.defn
class SimpleCodingAgent:
    @workflow.run
    async def run(self, task: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": task},
        ]

        # THE AGENT LOOP. Ask the model -> run any tools it asks for -> repeat.
        # The model decides which tool to call and when to stop; that model-driven
        # control flow is what makes this an agent and not a fixed workflow.
        for _ in range(20):  # guard: a confused model can't loop forever
            message: AssistantMessage = await workflow.execute_activity(
                llm_call,
                args=[MODEL, messages, TOOLS],
                start_to_close_timeout=_LLM_TIMEOUT,
            )  # typed + validated in the activity (pydantic data converter)
            messages.append(message.model_dump())  # send the dict form back next round

            if not message.tool_calls:
                return message.content or ""  # model answered -> done

            # The model may request several tools at once.
            for tc in message.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)  # args arrive as a JSON string

                if name == "read_file":
                    result = await workflow.execute_activity(
                        read_file, args["path"], start_to_close_timeout=_TOOL_TIMEOUT
                    )
                elif name == "write_file":
                    result = await workflow.execute_activity(
                        write_file,
                        args=[args["path"], args["content"]],
                        start_to_close_timeout=_TOOL_TIMEOUT,
                    )
                elif name == "run_command":
                    result = await workflow.execute_activity(
                        run_command, args["command"], start_to_close_timeout=_TOOL_TIMEOUT
                    )
                else:
                    result = f"unknown tool: {name}"

                # Feed each result back to the model, tagged with the call's id.
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
                )

        return "stopped: hit the 20-iteration limit"
