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

# Import the existing MCP server components
from mcp_server.server import use_memory_agent

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
                                            "description": "Natural language question"
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
                        question = arguments.get("question")
                        if not question:
                            return {
                                "jsonrpc": "2.0",
                                "id": id,
                                "error": {"code": -32602, "message": "Question required"}
                            }
                        
                        # Mock context
                        class MockContext:
                            async def report_progress(self, progress: int, total: Optional[int] = None):
                                pass
                        
                        try:
                            result = await use_memory_agent(question, MockContext())
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
                
                return {
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {"code": -32601, "message": "Method not found"}
                }
                
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }

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