import os
import sys
import threading
import time

from agent import Agent
from agent.schemas import Role
from agent.utils import extract_reply

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

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

    console = Console()
    console.print("[bold]Interactive Memory Agent CLI[/bold]")
    console.print("Type your message and press Enter. Type [bold]quit()[/bold] to exit.\n")

    def render_messages(messages):
        renderables = []
        for msg in messages:
            role = msg.role
            content = msg.content or ""

            # Detect environment/tool results encoded in <result> tags
            if role == Role.USER and content.strip().startswith("<result>"):
                # Extract inner content between <result> and </result>
                try:
                    inner = content.split("<result>", 1)[1].split("</result>", 1)[0].strip()
                except Exception:
                    inner = content
                syntax = Syntax(
                    inner,
                    "python",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                )
                renderables.append(
                    Panel(syntax, title="[magenta]environment[/magenta]", border_style="magenta")
                )
                continue

            if role == Role.SYSTEM:
                # Do not render system prompt/messages
                continue
            elif role == Role.USER:
                renderables.append(
                    Panel(Text(content, style="cyan"), title="[cyan]you[/cyan]", border_style="cyan")
                )
            elif role == Role.ASSISTANT:
                # Build a raw agent panel containing colorized think/python/reply blocks (with tags)
                def _slice_with_tags(text: str, start_tag: str, end_tag: str):
                    start = text.find(start_tag)
                    if start == -1:
                        return ""
                    end = text.find(end_tag, start)
                    if end == -1:
                        return ""
                    return text[start : end + len(end_tag)]

                think_block = _slice_with_tags(content, "<think>", "</think>")
                python_block = _slice_with_tags(content, "<python>", "</python>")
                reply_block = _slice_with_tags(content, "<reply>", "</reply>")
                reply_text = (extract_reply(content) or "").strip()

                raw_sections = []
                if think_block:
                    raw_sections.append(Text(think_block.strip(), style="yellow"))
                if python_block:
                    raw_sections.append(Text(python_block.strip(), style="blue"))
                if reply_block:
                    raw_sections.append(Text(reply_block.strip(), style="green"))

                if not raw_sections:
                    raw_sections.append(Text((content or "").strip(), style="green"))

                body = raw_sections[-1] if len(raw_sections) == 1 else Group(*raw_sections)
                renderables.append(
                    Panel(body, title="[green]agent[/green]", border_style="green")
                )

                # If there is a reply, add a second panel with just the reply text
                if reply_text:
                    renderables.append(
                        Panel(Text(reply_text, style="green"), title="[green]agent[/green]", border_style="green")
                    )
            else:
                renderables.append(Panel(Text(content), title=str(role)))

        return renderables

    def _clear_last_line():
        try:
            sys.stdout.write("\033[1A\033[2K")
            sys.stdout.flush()
        except Exception:
            pass

    while True:
        try:
            user_input = Console().input("[cyan]you[/cyan]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()  # newline
            break

        if user_input.lower() in {"quit()"}:
            break
        if not user_input:
            continue

        # Remove the raw input line so only Rich conversation panels remain
        _clear_last_line()

        # Run agent.chat in a background thread and live-render only THIS TURN's messages
        result_container = {"result": None, "error": None}
        start_index = len(agent.messages)

        def _run_agent():
            try:
                result_container["result"] = agent.chat(user_input)
            except Exception as e:
                result_container["error"] = e

        t = threading.Thread(target=_run_agent, daemon=True)
        t.start()

        with Live(Panel(Text("Waiting for agent...", style="yellow"), border_style="yellow"),
                  console=console, refresh_per_second=8) as live:
            while t.is_alive():
                messages_snapshot = list(agent.messages)[start_index:]
                panels = render_messages(messages_snapshot)
                body = panels[-1] if len(panels) == 1 else Group(*panels)
                live_renderable = Panel(
                    body,
                    title="Conversation",
                    border_style="white",
                )
                live.update(live_renderable, refresh=True)
                time.sleep(0.12)

            # One final update after the thread finishes
            messages_snapshot = list(agent.messages)[start_index:]
            panels = render_messages(messages_snapshot)
            body = panels[-1] if len(panels) == 1 else Group(*panels)
            live.update(Panel(body, title="Conversation", border_style="white"), refresh=True)

        t.join()

        if result_container["error"] is not None:
            console.print(f"[red]agent_error[/red]: {type(result_container['error']).__name__}: {result_container['error']}\n")


if __name__ == "__main__":
    main()


