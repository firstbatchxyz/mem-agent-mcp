import os
import sys


def get_repo_root() -> str:
    """Return absolute path to the repository root (two levels up from this file)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_default_memory_dir(repo_root: str) -> str:
    """Return a sensible default memory directory inside the repo."""
    return os.path.join(repo_root, "memory", "mcp-server")


def read_existing_memory_path(repo_root: str) -> str | None:
    """Read an existing .memory_path if present and valid, else None."""
    memory_path_file = os.path.join(repo_root, ".memory_path")
    try:
        if os.path.exists(memory_path_file):
            with open(memory_path_file, "r") as f:
                value = f.read().strip()
            value = os.path.expanduser(os.path.expandvars(value))
            if not os.path.isabs(value):
                value = os.path.abspath(os.path.join(repo_root, value))
            if os.path.isdir(value):
                return value
    except Exception:
        pass
    return None


def save_memory_path(repo_root: str, directory_path: str) -> None:
    """Persist the selected directory into .memory_path at the repo root."""
    memory_path_file = os.path.join(repo_root, ".memory_path")
    with open(memory_path_file, "w") as f:
        f.write(os.path.abspath(directory_path))
    print(f"Memory path saved to .memory_path: {directory_path}")


def choose_directory_with_tk(initialdir: str) -> str | None:
    """Open a native folder chooser via Tkinter; return the selected directory or None."""
    try:
        # Import lazily so environments without Tk can still run the module
        from tkinter import Tk, messagebox
        from tkinter.filedialog import askdirectory

        root = Tk()
        root.withdraw()
        root.update()

        selected = askdirectory(title="Select Memory Directory", initialdir=initialdir or "~")
        root.update()

        if not selected:
            return None

        selected = os.path.expanduser(os.path.expandvars(selected))
        if not os.path.isdir(selected):
            # Offer to create the directory
            create = messagebox.askyesno(
                title="Create Directory?",
                message=f"Directory does not exist:\n{selected}\n\nCreate it?",
            )
            if create:
                os.makedirs(selected, exist_ok=True)
            else:
                return None
        return os.path.abspath(selected)
    except Exception as exc:
        print(f"GUI selection failed: {type(exc).__name__}: {exc}")
        return None


def choose_directory_with_applescript(initialdir: str) -> str | None:
    """Fallback: macOS native folder chooser via AppleScript, returns path or None."""
    if sys.platform != "darwin":
        return None
    try:
        import subprocess

        script = (
            'tell application "System Events" to POSIX path of '
            '(choose folder with prompt "Select Memory Directory")'
        )
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=True
        )
        path = result.stdout.strip()
        if path:
            path = os.path.expanduser(os.path.expandvars(path))
            if not os.path.isdir(path):
                os.makedirs(path, exist_ok=True)
            return os.path.abspath(path)
        return None
    except Exception:
        return None


def main() -> int:
    repo_root = get_repo_root()
    default_dir = get_default_memory_dir(repo_root)
    existing = read_existing_memory_path(repo_root)
    initialdir = existing or default_dir

    # Try Tk first (native dialogs on most platforms)
    selected = choose_directory_with_tk(initialdir=initialdir)
    if not selected:
        # macOS native fallback via AppleScript
        selected = choose_directory_with_applescript(initialdir=initialdir)

    if not selected:
        print("No directory selected. You can run 'make setup-cli' to enter a path in the terminal.")
        return 1

    # Ensure directory exists
    try:
        os.makedirs(selected, exist_ok=True)
    except Exception as exc:
        print(f"Failed to create directory '{selected}': {exc}")
        return 1

    save_memory_path(repo_root, selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


