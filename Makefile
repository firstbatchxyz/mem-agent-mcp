# Set default target
.DEFAULT_GOAL := help

# Repository root (absolute)
REPO_ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)

# MLX Agent Names
MLX_4BIT_MEMORY_AGENT_NAME := mem-agent-mlx-4bit
MLX_8BIT_MEMORY_AGENT_NAME := mem-agent-mlx-8bit
MLX_MEMORY_AGENT_NAME := driaforall/mem-agent-mlx-bf16 
BF16_MEMORY_AGENT_SEARCH_NAME := mem-agent-mlx-bf16

# Help command
help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  1. help - Show this help message"
	@echo "  2. check-uv - Check if uv is installed and install if needed"
	@echo "  3. install - Install dependencies using uv"
	@echo "  4. setup - Choose memory directory via GUI and save to .memory_path"
	@echo "  5. add-filters - Add filters to .filters"
	@echo "  6. reset-filters - Reset filters in .filters"
	@echo "  7. run-agent - Run the agent"
	@echo "  8. generate-mcp-json - Generate the MCP.json file"
	@echo "  9. serve-mcp - Serve the MCP server"
	@echo "  10. chat-cli - Run interactive CLI to chat with the agent"

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
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		chmod +x mcp_server/scripts/install_lms.sh; \
		./mcp_server/scripts/install_lms.sh; \
	fi

setup:
	uv run python mcp_server/scripts/memory_setup.py && uv run python mcp_server/scripts/setup_scripts_and_json.py && chmod +x mcp_server/scripts/start_server.sh

add-filters:
	uv run python mcp_server/scripts/filters.py --add

reset-filters:
	uv run python mcp_server/scripts/filters.py --reset

run-agent:
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		echo "Detected macOS (Darwin). Starting MLX server via lms..."; \
		echo "Select MLX model precision:"; \
		echo "  1) 4-bit ($(MLX_4BIT_MEMORY_AGENT_NAME))"; \
		echo "  2) 8-bit ($(MLX_8BIT_MEMORY_AGENT_NAME))"; \
		echo "  3) bf16 ($(MLX_MEMORY_AGENT_NAME))"; \
		printf "Enter choice [1-3]: "; read choice; \
		case $$choice in \
			1) model=$(MLX_4BIT_MEMORY_AGENT_NAME); search_name=$(MLX_4BIT_MEMORY_AGENT_NAME);; \
			2) model=$(MLX_8BIT_MEMORY_AGENT_NAME); search_name=$(MLX_8BIT_MEMORY_AGENT_NAME);; \
			3) model=$(MLX_MEMORY_AGENT_NAME); search_name=$(BF16_MEMORY_AGENT_SEARCH_NAME);; \
			*) echo "Invalid choice. Defaulting to 4-bit."; model=$(MLX_4BIT_MEMORY_AGENT_NAME); search_name=$(MLX_4BIT_MEMORY_AGENT_NAME);; \
		esac; \
		printf "%s\n" "$$model" > $(REPO_ROOT)/.mlx_model_name; \
		echo "Saved model to $(REPO_ROOT)/.mlx_model_name: $$(cat $(REPO_ROOT)/.mlx_model_name)"; \
		lms get $$search_name --mlx --always-show-all-results; \
		lms load $$model; \
		lms server start --port 8000; \
	else \
		echo "Non-macOS detected. Starting vLLM server..."; \
		uv run vllm serve driaforall/mem-agent; \
	fi

generate-mcp-json:
	@echo "Generating mcp.json..."
	@echo '{"mcpServers": {"memory-agent-stdio": {"command": "bash", "args": ["-lc", "cd $(REPO_ROOT) && uv run python mcp_server/server.py"], "env": {"FASTMCP_LOG_LEVEL": "INFO", "MCP_TRANSPORT": "stdio"}, "timeout": 600000}}}' > mcp.json
	@echo "Wrote mcp.json the following contents:"
	@cat mcp.json

serve-mcp:
	@echo "Starting MCP server over STDIO"
	FASTMCP_LOG_LEVEL=INFO MCP_TRANSPORT=stdio uv run python -m mcp_server.server

chat-cli:
	uv run python chat_cli.py