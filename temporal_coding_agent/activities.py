import asyncio
import logging
from pathlib import Path

from temporalio import activity

logger = logging.getLogger(__name__)

# Every tool runs against this directory so the agent can't roam the whole
# filesystem. Created lazily on first use.
WORKDIR = Path(__file__).parent / "workspace"


def _resolve(path: str) -> Path:
    """Resolve `path` inside WORKDIR, refusing anything that escapes it."""
    WORKDIR.mkdir(exist_ok=True)
    root = WORKDIR.resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes workspace: {path}")
    return target


# Each of these is an ordinary Temporal activity. The workflow never calls them
# directly — they're handed to the agent via `activity_as_tool`, so the model
# decides when to invoke them and every call is a durable, retryable activity.


@activity.defn
async def read_file(path: str) -> str:
    """Read a text file from the workspace and return its contents."""
    logger.info("read_file: %s", path)
    target = _resolve(path)
    if not target.exists():
        return f"ERROR: file not found: {path}"
    return target.read_text(encoding="utf-8")


@activity.defn
async def write_file(path: str, content: str) -> str:
    """Create or overwrite a text file in the workspace."""
    logger.info("write_file: %s (%d chars)", path, len(content))
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


@activity.defn
async def run_command(command: str) -> str:
    """Run a shell command in the workspace and return exit code + output.

    NOTE: executes arbitrary shell commands on the host. Fine for a local dev
    demo; do not point this agent at untrusted input.
    """
    logger.info("run_command: %s", command)
    WORKDIR.mkdir(exist_ok=True)
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(WORKDIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace")
    return f"exit code: {proc.returncode}\n{output}"
