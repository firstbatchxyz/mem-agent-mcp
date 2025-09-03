import os, shutil, json

# Constants
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
print(f"Repo root: {REPO_ROOT}")

def resolve_uv_path() -> str:
    uv = os.environ.get("UV")  # set when invoked via `uv run`
    if uv:
        return uv
    uv_in_path = shutil.which("uv")
    if uv_in_path:
        return uv_in_path
    return "uv" 

START_SERVER_SCRIPT_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail

# Set working directory
cd "{repo_root}"

# Log startup for debugging
echo "INFO: Starting MCP wrapper script..." >&2
echo "INFO: Working directory: $(pwd)" >&2
echo "INFO: Using uv at: {uv_path}" >&2
echo "INFO: Python path: $({uv_path} run which python)" >&2

# Run the server with full path
exec {uv_path} run python mcp_server/server.py
"""

MCP_JSON_TEMPLATE = None  # unused; kept for backward-compatibility if imported elsewhere

def generate_start_server_script() -> None:
    """
    Generates the start_server.sh script and saves it inside
    mcp_server/scripts directory relative to the repo root.
    """
    uv_path = resolve_uv_path()
    script = START_SERVER_SCRIPT_TEMPLATE.format(repo_root=REPO_ROOT, uv_path=uv_path)
    
    try:    
        os.makedirs(os.path.join(REPO_ROOT, "mcp_server", "scripts"), exist_ok=True)
        start_script_path = os.path.join(REPO_ROOT, "mcp_server", "scripts", "start_server.sh")
        with open(start_script_path, "w") as f:
            f.write(script)
        try:
            os.chmod(start_script_path, 0o755)
        except Exception:
            pass
        print(f"Generated start_server.sh script in {os.path.join(REPO_ROOT, 'mcp_server', 'scripts')}")
    except Exception as e:
        print(f"Error generating start_server.sh script: {e}")

def generate_mcp_json() -> None:
    """
    Generates the mcp.json file and saves it at 
    the top level of the repo root.
    """
    config = {
        "mcpServers": {
            "memory-agent-stdio": {
                "command": os.path.join(REPO_ROOT, "mcp_server", "scripts", "start_server.sh"),
                "env": {
                    "FASTMCP_LOG_LEVEL": "INFO",
                    "MCP_TRANSPORT": "stdio",
                },
                "timeout": 600000,
            }
        }
    }
    mcp_json = json.dumps(config, indent=2)
    try:
        with open(os.path.join(REPO_ROOT, "mcp.json"), "w") as f:
            f.write(mcp_json)
        print(f"Generated mcp.json file in {REPO_ROOT}")
    except Exception as e:
        print(f"Error generating mcp.json file: {e}")

def main() -> None:
    generate_start_server_script()
    generate_mcp_json()

if __name__ == "__main__":
    main()