import asyncio
import logging
from pathlib import Path

import litellm
from temporalio import activity

from models import AssistantMessage

logger = logging.getLogger(__name__)

# Tools operate inside this dir so the agent can't roam the filesystem.
WORKDIR = Path(__file__).parent / "workspace"


# --- The model call, as one activity (cookbook-style) -----------------------


@activity.defn
async def llm_call(
    model: str, messages: list[dict], tools: list[dict]
) -> AssistantMessage:
    """One Claude call via LiteLLM. Returns the assistant message (validated).

    num_retries=0 so Temporal owns retries — otherwise LiteLLM would retry
    inside an activity that Temporal also retries (double-retry, double-bill).
    """
    logger.info("llm_call: %d messages", len(messages))
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        tools=tools,
        num_retries=0,
    )
    # Validate LiteLLM's raw message into our own stable, typed shape. Extra
    # fields LiteLLM adds (function_call, provider_specific_fields) are dropped.
    return AssistantMessage.model_validate(response.choices[0].message.model_dump())


# --- The tools, each its own activity ---------------------------------------


def _resolve(path: str) -> Path:
    WORKDIR.mkdir(exist_ok=True)
    root = WORKDIR.resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes workspace: {path}")
    return target


@activity.defn
async def read_file(path: str) -> str:
    logger.info("read_file: %s", path)
    target = _resolve(path)
    if not target.exists():
        return f"ERROR: file not found: {path}"
    return target.read_text(encoding="utf-8")


@activity.defn
async def write_file(path: str, content: str) -> str:
    logger.info("write_file: %s (%d chars)", path, len(content))
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


@activity.defn
async def run_command(command: str) -> str:
    logger.info("run_command: %s", command)
    WORKDIR.mkdir(exist_ok=True)
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(WORKDIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return f"exit code: {proc.returncode}\n{stdout.decode('utf-8', errors='replace')}"
