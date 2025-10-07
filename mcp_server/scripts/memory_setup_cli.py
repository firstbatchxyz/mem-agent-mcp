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
    print(f"✅ Memory path saved to .memory_path: {directory_path}")


def choose_directory_cli(initialdir: str) -> str | None:
    """Prompt user to enter a directory path via command line."""
    print("\n" + "=" * 60)
    print("📁 Memory Directory Setup (CLI Mode)")
    print("=" * 60)
    print(f"\nDefault directory: {initialdir}")
    print("\nPlease enter the path to your memory directory.")
    print("- Press ENTER to use the default directory")
    print("- Type a path (absolute or relative)")
    print("- Use ~ for home directory, e.g., ~/my-memories")
    print("=" * 60)
    
    user_input = input("\nMemory directory path: ").strip()
    
    # Use default if empty
    if not user_input:
        selected = initialdir
        print(f"\n✓ Using default directory: {selected}")
    else:
        selected = os.path.expanduser(os.path.expandvars(user_input))
        # Make it absolute if relative
        if not os.path.isabs(selected):
            selected = os.path.abspath(selected)
        print(f"\n✓ Selected directory: {selected}")
    
    # Check if directory exists, offer to create if not
    if not os.path.isdir(selected):
        print(f"\n⚠️  Directory does not exist: {selected}")
        response = input("Create it? [Y/n]: ").strip().lower()
        
        if response in ("", "y", "yes"):
            try:
                os.makedirs(selected, exist_ok=True)
                print(f"✅ Created directory: {selected}")
            except Exception as exc:
                print(f"❌ Failed to create directory: {exc}")
                return None
        else:
            print("❌ Directory not created. Setup cancelled.")
            return None
    else:
        print(f"✓ Directory exists: {selected}")
    
    return os.path.abspath(selected)


def main() -> int:
    repo_root = get_repo_root()
    default_dir = get_default_memory_dir(repo_root)
    existing = read_existing_memory_path(repo_root)
    initialdir = existing or default_dir
    
    if existing:
        print(f"\n📌 Existing memory path found: {existing}")
    
    selected = choose_directory_cli(initialdir=initialdir)
    
    if not selected:
        print("\n❌ No directory selected. Setup cancelled.")
        return 1
    
    # Ensure directory exists
    try:
        os.makedirs(selected, exist_ok=True)
    except Exception as exc:
        print(f"\n❌ Failed to create directory '{selected}': {exc}")
        return 1
    
    save_memory_path(repo_root, selected)
    print("\n" + "=" * 60)
    print("✅ Memory setup complete!")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

