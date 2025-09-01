import os
import sys

from agent import Agent

try:
    from mcp_server.settings import (
        MEMORY_AGENT_NAME,
        MLX_4BIT_MEMORY_AGENT_NAME,
    )
except Exception:
    # Fallback if executed in a different context
    MEMORY_AGENT_NAME = "driaforall/mem-agent"
    MLX_4BIT_MEMORY_AGENT_NAME = "mem-agent-mlx-quant"


def repo_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def read_memory_path() -> str:
    """
    Read the absolute memory directory path from .memory_path at repo root.
    If invalid or missing, fall back to repo_root/memory/mcp-server and warn.
    """
    root = repo_root()
    default_path = os.path.join(root, "memory", "mcp-server")
    memory_path_file = os.path.join(root, ".memory_path")

    try:
        if os.path.exists(memory_path_file):
            with open(memory_path_file, "r") as f:
                raw = f.read().strip()
            raw = os.path.expanduser(os.path.expandvars(raw))
            if not os.path.isabs(raw):
                raw = os.path.abspath(os.path.join(root, raw))
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
                ".memory_path not found. Run 'make setup'.\n"
                f"Falling back to default: {default_path}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(
            f"Warning: Failed to read .memory_path: {type(exc).__name__}: {exc}.\n"
            f"Falling back to default: {default_path}",
            file=sys.stderr,
        )

    os.makedirs(default_path, exist_ok=True)
    return os.path.abspath(default_path)


def pick_model_name() -> str:
    is_darwin = sys.platform == "darwin"
    return MLX_4BIT_MEMORY_AGENT_NAME if is_darwin else MEMORY_AGENT_NAME


def main() -> None:
    memory_path = read_memory_path()
    model_name = pick_model_name()

    agent = Agent(
        model=model_name,
        use_vllm=True,
        predetermined_memory_path=False,
        memory_path=memory_path,
    )

    print("Interactive Memory Agent CLI")
    print("Type your message and press Enter. Type quit() to exit.\n")

    while True:
        try:
            user_input = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()  # newline
            break

        if user_input.lower() in {"quit()"}:
            break
        if not user_input:
            continue

        try:
            result = agent.chat(user_input)
            reply = (result.reply or "").strip()
            print(f"agent: \n{reply}\n")
        except Exception as exc:
            print(f"agent_error: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()


