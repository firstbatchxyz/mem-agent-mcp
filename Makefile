# Set default target
.DEFAULT_GOAL := help

include .env

# Repository root (absolute)
REPO_ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)

# Help command
help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  1. help - Show this help message"
	@echo "  2. check-uv - Check if uv is installed and install if needed"
	@echo "  3. install - Install dependencies using uv"

# Check if uv is installed and install if needed
check-uv:
	@echo "Checking if uv is installed..."
	@if ! command -v uv > /dev/null; then \
		echo "uv not found. Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		echo "Please restart your shell or run 'source ~/.bashrc' (or ~/.zshrc) to use uv"; \
	else \
		echo "uv is already installed"; \
		uv --version; \
	fi

# Install dependencies using uv
install: check-uv
	@echo "Installing top-level workspace with uv..."
	uv sync

run-agent:
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		echo "Detected macOS (Darwin). Starting MLX server via lms..."; \
		lms load mem-agent-mlx-quant; \
		lms server start --port 8000; \
	else \
		echo "Non-macOS detected. Starting vLLM server..."; \
		uv run vllm serve driaforall/mem-agent; \
	fi

serve-mcp:
	uv run python -m mcp_server.server

generate-mcp-json:
	@echo "Generating mcp.json with repository root path..."
	@mkdir -p mcp_server
	@echo '{"mcpServers": {"memory-agent-stdio": {"command": "bash", "args": ["-lc", "cd $(REPO_ROOT) && uv run python mcp_server/server.py"], "env": {"FASTMCP_LOG_LEVEL": "INFO", "MCP_TRANSPORT": "stdio"}, "timeout": 600000}}}' > mcp.json
	@echo "Wrote mcp.json"