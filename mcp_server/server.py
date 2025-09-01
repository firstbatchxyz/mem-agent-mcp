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

from agent import Agent
try:
    from mcp_server.settings import MEMORY_AGENT_NAME
    from mcp_server.settings import MLX_MEMORY_AGENT_NAME
    from mcp_server.settings import MLX_4BIT_MEMORY_AGENT_NAME
except Exception:
    # Fallback when executed as a script from inside the package directory
    from settings import MEMORY_AGENT_NAME


# Initialize FastMCP (the installed version doesn't accept a timeout kwarg)
mcp = FastMCP("memory-agent-server")

# Initialize the agent
IS_DARWIN = sys.platform == "darwin"

agent = Agent(
    model=MEMORY_AGENT_NAME if not IS_DARWIN else MLX_4BIT_MEMORY_AGENT_NAME,
    use_vllm=True,
    predetermined_memory_path=True,
    memory_path="mcp-server",
)

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
        path = os.getenv("MCP_PATH", "/mcp-memory-agent")
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


