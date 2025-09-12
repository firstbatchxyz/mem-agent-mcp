#!/usr/bin/env python3
"""
HTTP wrapper for mem-agent MCP server.
Provides HTTP/SSE endpoint for ChatGPT integration while keeping the core stdio server unchanged.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
from contextlib import asynccontextmanager

# Add the repository root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import the existing MCP server components
from mcp_server.server import mcp, use_memory_agent

class MCPHTTPWrapper:
    """HTTP wrapper for the existing stdio MCP server."""
    
    def __init__(self):
        self.app = FastAPI(
            title="Mem-Agent MCP Server",
            description="HTTP wrapper for mem-agent MCP server - enables ChatGPT integration",
            version="1.0.0"
        )
        self.setup_middleware()
        self.setup_routes()
    
    def setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "*",  # Allow all origins for ngrok compatibility
                "https://chatgpt.com",
                "https://*.chatgpt.com", 
                "https://chat.openai.com"
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["*"]
        )
    
    def setup_routes(self):
        """Setup HTTP routes that mirror MCP functionality."""
        
        @self.app.get("/")
        async def root():
            return {
                "name": "mem-agent-mcp-server",
                "version": "1.0.0",
                "description": "Memory agent MCP server with HTTP interface",
                "endpoints": {
                    "/tools": "List available tools",
                    "/tools/{tool_name}": "Execute a specific tool"
                }
            }
        
        @self.app.get("/v1/tools")
        async def list_tools():
            """List available MCP tools - MCP protocol endpoint."""
            return {
                "tools": [
                    {
                        "name": "use_memory_agent",
                        "description": "Query the local memory agent with natural language questions",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The user query to be processed by the agent"
                                }
                            },
                            "required": ["question"]
                        }
                    }
                ]
            }
        
        @self.app.get("/tools")
        async def list_tools_legacy():
            """Legacy endpoint for compatibility."""
            return await list_tools()
        
        async def _execute_memory_agent_logic(request_data: dict):
            """Core logic for executing memory agent."""
            question = request_data.get("question")
            if not question:
                raise HTTPException(status_code=400, detail="Question parameter is required")
            
            # Create a mock context for the existing MCP function
            class MockContext:
                async def report_progress(self, progress: int, total: Optional[int] = None):
                    pass  # No-op for HTTP interface
            
            # Call the existing MCP tool function
            result = await use_memory_agent(question, MockContext())
            
            return {
                "result": result,
                "tool": "use_memory_agent",
                "success": True
            }
        
        @self.app.post("/v1/tools/use_memory_agent")
        async def execute_memory_agent_v1(request_data: dict):
            """Execute the memory agent tool - MCP protocol endpoint."""
            try:
                return await _execute_memory_agent_logic(request_data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error executing memory agent: {str(e)}")
        
        @self.app.post("/tools/use_memory_agent")
        async def execute_memory_agent(request_data: dict):
            """Execute the memory agent tool."""
            try:
                return await _execute_memory_agent_logic(request_data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error executing memory agent: {str(e)}")
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "server": "mem-agent-mcp"}

def create_app() -> FastAPI:
    """Create the FastAPI application."""
    wrapper = MCPHTTPWrapper()
    return wrapper.app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    print("🌐 Starting Mem-Agent MCP HTTP Server...")
    print("📝 This is an HTTP wrapper for ChatGPT integration")
    print("💻 The original stdio server remains unchanged for Claude Desktop/Code")
    print()
    print("🔗 Endpoints:")
    print("  - GET  /         : Server info")
    print("  - GET  /tools    : List available tools") 
    print("  - POST /tools/use_memory_agent : Query memory agent")
    print("  - GET  /health   : Health check")
    print()
    print("🌍 Once running, use ngrok to expose for ChatGPT:")
    print("  ngrok http 8080")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Allow external access via ngrok
        port=8080,
        log_level="info"
    )