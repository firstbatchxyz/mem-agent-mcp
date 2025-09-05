# mem-agent-mcp

## Running Instructions

1. `make check-uv`
2. `make install`
3. `make setup`
4. `make run-agent`
5. `make generate-mcp-json`
6. Instructions per app/provider:
    - Claude Desktop:
        - Copy the generated `mcp.json` to the wherever your `claude_desktop.json` is located, then, quit and restart Claude Desktop.
    - Lm Studio:
        - Copy the generated `mcp.json` to the `mcp.json` of Lm Studio, and it should work. If there are problems, change the name of the model in .mlx_model_name from `mem-agent-mlx-4bit` or `mem-agent-mlx-8bit` to `mem-agent-mlx@4bit` or `mem-agent-mlx@8bit` respectively.



