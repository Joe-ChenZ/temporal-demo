from typing import Optional

from pydantic import BaseModel

# Our own stable, typed shape for the parts of an assistant message we use.
# llm_call validates LiteLLM's raw output into these, so the workflow codes
# against typed attributes (message.tool_calls, tc.function.name) instead of
# guessing dict keys. Extra fields LiteLLM includes are simply ignored.


class FunctionCall(BaseModel):
    name: str
    arguments: str  # the tool arguments, as a JSON string the model emitted


class ToolCall(BaseModel):
    id: str  # echoed back as tool_call_id so the model pairs result→request
    type: str = "function"
    function: FunctionCall


class AssistantMessage(BaseModel):
    role: str
    content: Optional[str] = None  # text answer, or None when calling tools
    tool_calls: Optional[list[ToolCall]] = None
