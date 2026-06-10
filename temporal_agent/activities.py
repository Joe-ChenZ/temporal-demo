import asyncio
import ast
import logging
import operator
import os

from google import genai
from google.genai import types
from temporalio import activity

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You are a helpful assistant. You have access to two tools: "
    "'calculate' for math expressions and 'get_weather' for current weather. "
    "Use them when relevant. Be concise."
)

_TOOL_CONFIG = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="calculate",
        description="Evaluate a mathematical expression and return the result.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "expression": types.Schema(
                    type=types.Type.STRING,
                    description="A Python-style math expression, e.g. '144 * 37' or '(10 + 5) / 3'",
                )
            },
            required=["expression"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_weather",
        description="Get the current weather for a city.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "city": types.Schema(
                    type=types.Type.STRING,
                    description="The city name, e.g. 'Tokyo' or 'New York'",
                )
            },
            required=["city"],
        ),
    ),
])

# Safe math eval — only allows numeric literals and basic operators
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return _SAFE_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    return _eval(ast.parse(expr, mode="eval").body)


@activity.defn
async def call_llm(messages: list[dict]) -> dict:
    logger.info("calling LLM (%d messages in history)", len(messages))
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash",
        contents=messages,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[_TOOL_CONFIG],
        ),
    )

    candidate = response.candidates[0]
    parts = []
    tool_calls = []
    text = None

    for part in candidate.content.parts:
        if part.text:
            text = part.text
            parts.append({"text": part.text})
        elif part.function_call:
            fc = part.function_call
            tool_calls.append({"name": fc.name, "args": dict(fc.args)})
            parts.append({"function_call": {"name": fc.name, "args": dict(fc.args)}})

    logger.info("LLM responded: has_tool_calls=%s", bool(tool_calls))
    return {
        "has_tool_calls": bool(tool_calls),
        "text": text,
        "tool_calls": tool_calls,
        "model_message": {"role": "model", "parts": parts},
    }


@activity.defn
async def calculate(expression: str) -> str:
    logger.info("calculating: %s", expression)
    await asyncio.sleep(1)
    result = _safe_eval(expression)
    formatted = int(result) if isinstance(result, float) and result.is_integer() else result
    logger.info("result: %s", formatted)
    return str(formatted)


@activity.defn
async def get_weather(city: str) -> str:
    logger.info("fetching weather for %s", city)
    await asyncio.sleep(2)
    conditions = {
        "tokyo": "Partly cloudy, 68°F (20°C)",
        "new york": "Sunny, 75°F (24°C)",
        "london": "Overcast, 58°F (14°C)",
        "sydney": "Clear, 82°F (28°C)",
        "paris": "Light rain, 61°F (16°C)",
    }
    result = conditions.get(city.lower(), "Sunny, 72°F (22°C)")
    logger.info("weather for %s: %s", city, result)
    return result
