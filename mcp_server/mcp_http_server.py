#!/usr/bin/env python3
"""
MCP-compliant HTTP server for ChatGPT integration.
Implements the Model Context Protocol over HTTP/SSE as expected by ChatGPT.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import uvicorn

# Add the repository root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import the core components from the agent package
import platform
from agent import Agent

# Import settings
try:
    from mcp_server.settings import MEMORY_AGENT_NAME, MLX_4BIT_MEMORY_AGENT_NAME
except ImportError:
    from settings import MEMORY_AGENT_NAME
    MLX_4BIT_MEMORY_AGENT_NAME = "mem-agent-mlx@4bit"

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
    """Run the memory agent with the given question."""
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
        result = await fut
        return (result.reply or "").strip()
    except Exception as exc:
        return f"agent_error: {type(exc).__name__}: {exc}"

class MCPServer:
    """MCP-compliant HTTP server for ChatGPT integration."""
    
    def __init__(self):
        self.app = FastAPI(
            title="Mem-Agent MCP Server",
            description="MCP-compliant server for ChatGPT integration",
            version="1.0.0"
        )
        self.setup_middleware()
        self.setup_routes()
    
    def setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    async def handle_mcp_request(self, data: dict):
        """Handle MCP JSON-RPC requests."""
        method = data.get("method")
        params = data.get("params", {})
        id = data.get("id")
        
        if method == "initialize":
            return {
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
        
        elif method == "tools/list":
            return {
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
                                    "description": "Natural language question to search your memory"
                                }
                            },
                            "required": ["question"]
                        }
                    }]
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "use_memory_agent":
                try:
                    question = arguments.get("question")
                    if not question:
                        return {
                            "jsonrpc": "2.0",
                            "id": id,
                            "error": {"code": -32602, "message": "Question required"}
                        }
                    
                    result = await run_memory_agent(question)
                    return {
                        "jsonrpc": "2.0",
                        "id": id,
                        "result": {
                            "content": [{"type": "text", "text": result}]
                        }
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": {"code": -32603, "message": str(e)}
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            }

    def setup_routes(self):
        """Setup MCP protocol routes."""
        
        @self.app.post("/")
        async def root_post(request: Request):
            """Handle POST requests to root - ChatGPT posts here."""
            print("🔍 Received POST to root")
            try:
                data = await request.json()
                print(f"📨 Request data: {json.dumps(data, indent=2)}")
                result = await self.handle_mcp_request(data)
                print(f"📤 Response: {json.dumps(result, indent=2)}")
                return result
            except Exception as e:
                print(f"❌ Error in root POST: {e}")
                return {"error": str(e)}
        
        
        @self.app.post("/mcp")
        async def mcp_endpoint(request: Request):
            """Main MCP endpoint for ChatGPT integration."""
            try:
                data = await request.json()
                return await self.handle_mcp_request(data)
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": data.get("id") if 'data' in locals() else None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
        
        @self.app.get("/")
        async def root():
            return {
                "name": "mem-agent-mcp-server",
                "version": "1.0.0",
                "protocol": "MCP over HTTP",
                "endpoint": "/mcp"
            }
        
        @self.app.head("/")
        async def root_head():
            """Handle HEAD requests from ChatGPT."""
            return Response(status_code=200)
        
        @self.app.options("/mcp")
        async def mcp_options():
            """Handle OPTIONS requests for CORS preflight."""
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
            )
        
        @self.app.get("/mcp")
        async def mcp_get():
            """Handle GET requests to MCP endpoint."""
            return {
                "protocol": "Model Context Protocol",
                "version": "2024-11-05",
                "methods": ["initialize", "tools/list", "tools/call"]
            }
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "protocol": "MCP"}
        
        @self.app.head("/health") 
        async def health_head():
            return Response(status_code=200)

def create_app() -> FastAPI:
    """Create the MCP FastAPI application."""
    server = MCPServer()
    return server.app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    print("🌐 Starting MCP-Compliant HTTP Server for ChatGPT...")
    print("📋 This implements the Model Context Protocol over HTTP")
    print("🔗 Main endpoint: POST /mcp")
    print()
    print("🌍 Use with ngrok for ChatGPT:")
    print("  1. ngrok http 8081")
    print("  2. Add ngrok URL + '/mcp' to ChatGPT")
    print("  3. Protocol: HTTP (not SSE)")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,  # Different port to avoid conflicts
        log_level="info"
    )