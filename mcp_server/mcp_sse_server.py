#!/usr/bin/env python3
"""
MCP Server-Sent Events server for ChatGPT integration.
Implements MCP over SSE as preferred by ChatGPT.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse
import uvicorn

# Add the repository root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Try to import FastMCP version first (for compatibility), fall back to direct Agent usage
try:
    from mcp_server.server import use_memory_agent
    FASTMCP_AVAILABLE = True
    print("✅ FastMCP version available")
except Exception as e:
    FASTMCP_AVAILABLE = False
    print(f"⚠️  FastMCP not available ({e}), using direct Agent")

# Import agent components for fallback
import platform
from agent import Agent

IS_DARWIN = platform.system() == "Darwin"
FILTERS_PATH = os.path.join(REPO_ROOT, ".filters")

def _read_memory_path() -> str:
    """Read the absolute memory directory path from .memory_path at repo root."""
    default_path = os.path.join(REPO_ROOT, "memory", "mcp-server")
    memory_path_file = os.path.join(REPO_ROOT, ".memory_path")

    try:
        if os.path.exists(memory_path_file):
            with open(memory_path_file, "r") as f:
                raw = f.read().strip()
            raw = os.path.expanduser(os.path.expandvars(raw))
            if not os.path.isabs(raw):
                raw = os.path.abspath(os.path.join(REPO_ROOT, raw))
            if os.path.isdir(raw):
                return raw
        print(f"⚠️  Memory path not found or invalid, using default: {default_path}")
        return default_path
    except Exception as e:
        print(f"⚠️  Error reading memory path: {e}, using default: {default_path}")
        return default_path

def _read_mlx_model_name(fallback: str) -> str:
    """Read MLX model name from .mlx_model_name file."""
    try:
        mlx_model_file = os.path.join(REPO_ROOT, ".mlx_model_name")
        if os.path.exists(mlx_model_file):
            with open(mlx_model_file, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return fallback

def _read_filters() -> str:
    """Read filters from .filters file."""
    try:
        if os.path.exists(FILTERS_PATH):
            with open(FILTERS_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""

async def run_memory_agent(question: str) -> str:
    """Run the memory agent with the given question (non-blocking)."""
    try:
        try:
            from mcp_server.settings import MEMORY_AGENT_NAME, MLX_4BIT_MEMORY_AGENT_NAME
        except Exception:
            from settings import MEMORY_AGENT_NAME
            MLX_4BIT_MEMORY_AGENT_NAME = "mem-agent-mlx@4bit"

        agent = Agent(
            model=(MEMORY_AGENT_NAME if not IS_DARWIN else _read_mlx_model_name(MLX_4BIT_MEMORY_AGENT_NAME)),
            use_vllm=True,
            predetermined_memory_path=False,
            memory_path=_read_memory_path(),
        )

        filters = _read_filters()
        if len(filters) > 0:
            question = question + "\n\n" + "<filter>" + filters + "</filter>"

        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, agent.chat, question)
        result = await fut
        return (result.reply or "").strip()
    except Exception as exc:
        return f"agent_error: {type(exc).__name__}: {exc}"

class MCPSSEServer:
    """MCP Server-Sent Events server for ChatGPT."""
    
    def __init__(self):
        self.app = FastAPI(
            title="Mem-Agent MCP SSE Server",
            description="MCP over Server-Sent Events for ChatGPT",
            version="1.0.0"
        )
        self.setup_middleware()
        self.setup_routes()
    
    def setup_middleware(self):
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Setup SSE MCP routes."""
        
        @self.app.get("/")
        async def root():
            return {
                "name": "mem-agent-mcp-sse",
                "protocol": "MCP over Server-Sent Events",
                "version": "1.0.0"
            }
        
        @self.app.head("/")
        async def root_head():
            return Response(status_code=200)
        
        @self.app.get("/sse")
        async def sse_endpoint(request: Request):
            """Server-Sent Events endpoint for MCP."""
            
            async def event_publisher():
                # Send initial connection
                yield {
                    "event": "connection",
                    "data": json.dumps({
                        "type": "connection",
                        "protocol": "MCP",
                        "version": "2024-11-05"
                    })
                }
                
                # Wait for requests (in real implementation, this would handle incoming messages)
                # For now, just send a ready signal
                yield {
                    "event": "ready", 
                    "data": json.dumps({
                        "type": "ready",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "mem-agent-mcp",
                            "version": "1.0.0"
                        }
                    })
                }
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(30)
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "ping"})
                    }
            
            return EventSourceResponse(event_publisher())
        
        @self.app.post("/message")
        async def handle_message(request: Request):
            """Handle MCP messages via POST."""
            try:
                data = await request.json()
                print("📨 MCP POST /message:", json.dumps(data, indent=2))
                method = data.get("method")
                params = data.get("params", {})
                id = data.get("id")
                
                if method == "initialize":
                    result = {
                        "jsonrpc": "2.0",
                        "id": id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {
                                "name": "mem-agent-mcp",
                                "version": "1.0.0"
                            }
                        }
                    }
                    print("📤 initialize result:", json.dumps(result, indent=2))
                    return result
                
                elif method == "tools/list":
                    result = {
                        "jsonrpc": "2.0",
                        "id": id,
                        "result": {
                            "tools": [{
                                "name": "use_memory_agent",
                                "description": "Query your personal memory and conversation history",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "question": {
                                            "type": "string",
                                            "description": "Natural language question"
                                        }
                                    },
                                    "required": ["question"]
                                }
                            }]
                        }
                    }
                    print("📤 tools/list result:", json.dumps(result, indent=2))
                    return result
                
                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    
                    if tool_name == "use_memory_agent":
                        question = arguments.get("question")
                        if not question:
                            result = {
                                "jsonrpc": "2.0",
                                "id": id,
                                "error": {"code": -32602, "message": "Question required"}
                            }
                            print("📤 tools/call error:", json.dumps(result, indent=2))
                            return result
                        
                        try:
                            # FastMCP decorated functions can't be called directly in HTTP context
                            # Use direct Agent approach for HTTP/SSE servers
                            result_text = await run_memory_agent(question)
                            print("✅ Used direct Agent (HTTP context)")
                                
                            result = {
                                "jsonrpc": "2.0",
                                "id": id,
                                "result": {
                                    "content": [{"type": "text", "text": result_text}]
                                }
                            }
                            print("📤 tools/call result:", json.dumps(result, indent=2))
                            return result
                        except Exception as e:
                            result = {
                                "jsonrpc": "2.0",
                                "id": id,
                                "error": {"code": -32603, "message": str(e)}
                            }
                            print("📤 tools/call exception:", json.dumps(result, indent=2))
                            return result
                
                result = {
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {"code": -32601, "message": "Method not found"}
                }
                print("📤 method not found:", json.dumps(result, indent=2))
                return result
                
            except Exception as e:
                err = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                print("❌ parse error:", e)
                return err

        # Some MCP clients POST JSON-RPC messages to the same path as the SSE stream.
        # Mirror the /message handler at /sse to avoid 405s when clients POST /sse.
        @self.app.post("/sse")
        async def sse_post(request: Request):
            return await handle_message(request)

def create_app() -> FastAPI:
    """Create the SSE MCP FastAPI application."""
    server = MCPSSEServer()
    return server.app

app = create_app()

if __name__ == "__main__":
    print("🌊 Starting MCP Server-Sent Events Server...")
    print("🔗 SSE endpoint: http://localhost:8082/sse")
    print("📮 Message endpoint: http://localhost:8082/message")
    print()
    print("📋 For ChatGPT:")
    print("  1. ngrok http 8082")
    print("  2. Use: https://your-url.ngrok.io/sse")
    print("  3. Protocol: SSE")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")
