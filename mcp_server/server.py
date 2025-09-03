import os
import sys
import socket
import asyncio
from typing import Optional

from fastmcp import FastMCP, Context

# Ensure repository root is on sys.path so we can import the `agent` package
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FILTERS_PATH = os.path.join(REPO_ROOT, ".filters")

from agent import Agent
try:
    from mcp_server.settings import MEMORY_AGENT_NAME
    from mcp_server.settings import MLX_4BIT_MEMORY_AGENT_NAME
except Exception:
    # Fallback when executed as a script from inside the package directory
    from settings import MEMORY_AGENT_NAME
    MLX_4BIT_MEMORY_AGENT_NAME = "mem-agent-mlx@4bit"


# Initialize FastMCP (the installed version doesn't accept a timeout kwarg)
mcp = FastMCP("memory-agent-server")

def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read_memory_path() -> str:
    """
    Read the absolute memory directory path from .memory_path at repo root.
    If invalid or missing, fall back to repo_root/memory/mcp-server and warn.
    """
    repo_root = _repo_root()
    default_path = os.path.join(repo_root, "memory", "mcp-server")
    memory_path_file = os.path.join(repo_root, ".memory_path")

    try:
        if os.path.exists(memory_path_file):
            with open(memory_path_file, "r") as f:
                raw = f.read().strip()
            raw = os.path.expanduser(os.path.expandvars(raw))
            if not os.path.isabs(raw):
                raw = os.path.abspath(os.path.join(repo_root, raw))
            if os.path.isdir(raw):
                return raw
            else:
                print(
                    f"Warning: Path in .memory_path is not a directory: {raw}.\n"
                    f"Falling back to default: {default_path}",
                    file=sys.stderr,
                )
        else:
            print(
                ".memory_path not found. Run 'make setup' or 'make setup-cli'.\n"
                f"Falling back to default: {default_path}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(
            f"Warning: Failed to read .memory_path: {type(exc).__name__}: {exc}.\n"
            f"Falling back to default: {default_path}",
            file=sys.stderr,
        )

    # Ensure fallback exists
    try:
        os.makedirs(default_path, exist_ok=True)
    except Exception:
        pass
    return os.path.abspath(default_path)


# Initialize the agent
IS_DARWIN = sys.platform == "darwin"

def _read_mlx_model_name(default_model: str) -> str:
    """
    Read the MLX model name from .mlx_model_name at repo root.
    Falls back to the provided default when missing/invalid.
    """
    repo_root = _repo_root()
    model_file = os.path.join(repo_root, ".mlx_model_name")
    try:
        if os.path.exists(model_file):
            with open(model_file, "r") as f:
                raw = f.read().strip()
            # Strip surrounding quotes if present
            if raw.startswith("\"") and raw.endswith("\"") and len(raw) >= 2:
                raw = raw[1:-1]
            if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
                raw = raw[1:-1]
            if raw:
                return raw
    except Exception:
        pass
    return default_model

def _read_filters() -> str:
    """
    Read the filters from .filters at repo root.
    """
    try:
        with open(FILTERS_PATH, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

@mcp.tool
async def use_memory_agent(question: str, ctx: Context) -> str:
    """
    Provide the local memory agent with the user query 
    so that it can (or not) interact with the memory and 
    return the response from the agent. YOU HAVE TO PASS
    THE USER QUERY AS IS, WITHOUT ANY MODIFICATIONS. 
    
    For instance, if the user query is "I'm happy that today is my birthday",
    you will call the tool with the following parameters:
    {"question": "I'm happy that today is my birthday"}.

    MAKE NO MODIFICATIONS TO THE USER QUERY.

    Args:
        question: The user query to be processed by the agent.

    Returns:
        The response from the agent.
    """
    try:
        agent = Agent(
            model=(
                MEMORY_AGENT_NAME if not IS_DARWIN else _read_mlx_model_name(MLX_4BIT_MEMORY_AGENT_NAME)
            ),
            use_vllm=True,
            predetermined_memory_path=False,
            memory_path=_read_memory_path(),
        )

        filters = _read_filters()

        if len(filters) > 0:
            question = question + "\n\n" + "<filter>" + filters + "</filter>"

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, agent.chat, question)

        # heartbeat loop: indeterminate progress
        while not fut.done():
            await ctx.report_progress(progress=1)   # no total -> indeterminate
            await asyncio.sleep(2)

        result = await fut
        await ctx.report_progress(progress=1, total=1)  # 100%
        return (result.reply or "").strip()
    except Exception as exc:
        return f"agent_error: {type(exc).__name__}: {exc}"


if __name__ == "__main__":
    # Configure transport from environment; default to stdio when run by a client
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()

    if transport == "http":
        host = os.getenv("MCP_HOST", "127.0.0.1")
        path = os.getenv("MCP_PATH", "/mcp/")
        port_str = os.getenv("MCP_PORT", "")

        # If no port provided (or set to 0), choose a free one to avoid conflicts
        if not port_str or port_str == "0":
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, 0))
                port = s.getsockname()[1]
        else:
            try:
                port = int(port_str)
            except ValueError:
                # Fallback to a free port if invalid value provided
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, 0))
                    port = s.getsockname()[1]

        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        # Use stdio transport by default or when explicitly requested
        mcp.run(transport="stdio")


