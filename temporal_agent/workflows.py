from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import calculate, call_llm, get_weather

_TOOL_TIMEOUT = timedelta(seconds=30)
_LLM_TIMEOUT = timedelta(seconds=60)
_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class AgentSessionWorkflow:
    def __init__(self) -> None:
        self._history: list[dict] = []
        self._pending_message: str | None = None
        self._last_response: str | None = None
        self._response_count: int = 0
        self._is_processing: bool = False

    @workflow.signal
    async def send_message(self, text: str) -> None:
        self._pending_message = text

    @workflow.query
    def get_state(self) -> dict:
        return {
            "last_response": self._last_response,
            "response_count": self._response_count,
            "is_processing": self._is_processing,
        }

    @workflow.run
    async def run(self, session_id: str) -> None:
        self._history = []

        while True:
            await workflow.wait_condition(lambda: self._pending_message is not None)
            user_text = self._pending_message
            self._pending_message = None
            self._is_processing = True

            self._history.append({"role": "user", "parts": [{"text": user_text}]})

            # Agentic tool loop — keep going until Gemini stops requesting tools
            while True:
                response = await workflow.execute_activity(
                    call_llm,
                    args=[self._history],
                    start_to_close_timeout=_LLM_TIMEOUT,
                    retry_policy=_RETRY,
                )

                self._history.append(response["model_message"])

                if not response["has_tool_calls"]:
                    self._last_response = response["text"]
                    break

                # Dispatch each tool call as a Temporal activity
                tool_result_parts = []
                for tc in response["tool_calls"]:
                    name = tc["name"]
                    args = tc["args"]

                    if name == "calculate":
                        result = await workflow.execute_activity(
                            calculate,
                            args["expression"],
                            start_to_close_timeout=_TOOL_TIMEOUT,
                            retry_policy=_RETRY,
                        )
                    elif name == "get_weather":
                        result = await workflow.execute_activity(
                            get_weather,
                            args["city"],
                            start_to_close_timeout=_TOOL_TIMEOUT,
                            retry_policy=_RETRY,
                        )
                    else:
                        result = f"Unknown tool: {name}"

                    tool_result_parts.append({
                        "function_response": {
                            "name": name,
                            "response": {"result": result},
                        }
                    })

                self._history.append({"role": "user", "parts": tool_result_parts})

            self._response_count += 1
            self._is_processing = False
