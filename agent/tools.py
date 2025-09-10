import os
import tempfile
import uuid
import subprocess
from pathlib import Path
from typing import Union

from agent.settings import MEMORY_PATH
from agent.utils import check_size_limits, create_memory_if_not_exists

def get_size(file_or_dir_path: str) -> int:
    """
    Get the size of a file or directory.

    Args:
        file_or_dir_path: The path to the file or directory. 
                          If empty string, returns total memory directory size.

    Returns:
        The size of the file or directory in bytes.
    """
    # Handle empty string by returning total memory size
    if not file_or_dir_path or file_or_dir_path == "":
        # Get the current working directory (which should be the memory root)
        cwd = os.getcwd()
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(cwd):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except OSError:
                    pass
        return total_size
    
    # Otherwise check the specific path
    if os.path.isfile(file_or_dir_path):
        return os.path.getsize(file_or_dir_path)
    elif os.path.isdir(file_or_dir_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(file_or_dir_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except OSError:
                    pass
        return total_size
    else:
        raise FileNotFoundError(f"Path not found: {file_or_dir_path}")

def create_file(file_path: str, content: str = "") -> bool:
    """
    Create a new file in the memory with the given content (if any).
    First create a temporary file with the given content, check if 
    the size limits are respected, if so, move the temporary file to 
    the final destination.

    Args:
        file_path: The path to the file.
        content: The content of the file.

    Returns:
        True if the file was created successfully, False otherwise.
    """
    temp_file_path = None
    try:
        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Create a unique temporary file name in the same directory as the target file
        # This ensures the temp file is within the sandbox's allowed path
        target_dir = os.path.dirname(os.path.abspath(file_path)) or "."
        temp_file_path = os.path.join(target_dir, f"temp_{uuid.uuid4().hex[:8]}.txt")
        
        with open(temp_file_path, "w") as f:
            f.write(content)
        
        if check_size_limits(temp_file_path):
            # Move the content to the final destination
            with open(file_path, "w") as f:
                f.write(content)
            os.remove(temp_file_path)
            return True
        else:
            os.remove(temp_file_path)
            raise Exception(f"File {file_path} is too large to create")
    except Exception as e:
        # Clean up temp file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                raise Exception(f"Error removing temp file {temp_file_path}: {e}")
        raise Exception(f"Error creating file {file_path}: {e}")
    
def create_dir(dir_path: str) -> bool:
    """
    Create a new directory in the memory.

    Args:
        dir_path: The path to the directory.

    Returns:
        True if the directory was created successfully, False otherwise.
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception:
        return False


def update_file(file_path: str, old_content: str, new_content: str) -> Union[bool, str]:
    """
    Simple find-and-replace update method for files.

    This is an easier alternative to write_to_file() that doesn't require
    creating git-style diffs. It performs a simple string replacement.

    Parameters
    ----------
    file_path : str
        Path to the file to update.
    old_content : str
        The exact text to find and replace in the file.
    new_content : str
        The text to replace old_content with.

    Returns
    -------
    Union[bool, str]
        True if successful, error message string if failed.

    Examples
    --------
    # Add a new row to a table
    old = "| TKT-1056  | 2024-09-25 | Late Delivery   | Resolved |"
    new = "| TKT-1056  | 2024-09-25 | Late Delivery   | Resolved |\\n| TKT-1057  | 2024-11-11 | Damaged Item    | Open     |"
    result = update_file("user.md", old, new)
    """
    try:
        # Read the current file content
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist"

        if not os.path.isfile(file_path):
            return f"Error: '{file_path}' is not a file"

        with open(file_path, "r") as f:
            current_content = f.read()

        # Check if old_content exists in the file
        if old_content not in current_content:
            # Provide helpful context about what wasn't found
            preview_length = 50
            preview = old_content[:preview_length] + "..." if len(old_content) > preview_length else old_content
            return f"Error: Could not find the specified content in the file. Looking for: '{preview}'"

        # Count occurrences to warn about multiple matches
        occurrences = current_content.count(old_content)
        if occurrences > 1:
            # Still proceed but warn the user
            print(f"Warning: Found {occurrences} occurrences of the content. Replacing only the first one.")

        # Perform the replacement (only first occurrence)
        updated_content = current_content.replace(old_content, new_content, 1)

        # Check if replacement actually changed anything
        if updated_content == current_content:
            return "Error: No changes were made to the file"

        # Write the updated content back
        with open(file_path, "w") as f:
            f.write(updated_content)

        return True

    except PermissionError:
        return f"Error: Permission denied writing to '{file_path}'"
    except Exception as e:
        return f"Error: Unexpected error - {str(e)}"

def read_file(file_path: str) -> str:
    """
    Read a file in the memory.

    Args:
        file_path: The path to the file.

    Returns:
        The content of the file, or an error message if the file cannot be read.
    """
    try:
        # Ensure the file path is properly resolved
        if not os.path.exists(file_path):
            return f"Error: File {file_path} does not exist"
        
        if not os.path.isfile(file_path):
            return f"Error: {file_path} is not a file"
            
        with open(file_path, "r") as f:
            return f.read()
    except PermissionError:
        return f"Error: Permission denied accessing {file_path}"
    except Exception as e:
        return f"Error: {e}"
    
def list_files() -> str:
    """
    Display all files and directories in the current working directory as a tree structure.
    
    Example output:
    ```
    ./
    ├── user.md
    └── entities/
        ├── 452_willow_creek_dr.md
        └── frank_miller_plumbing.md
    ```

    Returns:
        A string representation of the directory tree.
    """
    try:
        # Always use current working directory
        dir_path = os.getcwd()
        
        def build_tree(start_path, prefix="", is_last=True):
            """Recursively build tree structure"""
            entries = []
            try:
                items = sorted(os.listdir(start_path))
                # Filter out hidden files and __pycache__
                items = [item for item in items if not item.startswith('.') and item != '__pycache__']
            except PermissionError:
                return f"{prefix}[Permission Denied]\n"
            
            if not items:
                return ""
            
            for i, item in enumerate(items):
                item_path = os.path.join(start_path, item)
                is_last_item = i == len(items) - 1
                
                # Choose the right prefix characters
                if is_last_item:
                    current_prefix = prefix + "└── "
                    extension = prefix + "    "
                else:
                    current_prefix = prefix + "├── "
                    extension = prefix + "│   "
                
                if os.path.isdir(item_path):
                    # Check if directory is empty
                    try:
                        dir_contents = [f for f in os.listdir(item_path) 
                                      if not f.startswith('.') and f != '__pycache__']
                        if not dir_contents:
                            entries.append(f"{current_prefix}{item}/ (empty)\n")
                        else:
                            entries.append(f"{current_prefix}{item}/\n")
                            # Recursively add subdirectory contents
                            entries.append(build_tree(item_path, extension, is_last_item))
                    except PermissionError:
                        entries.append(f"{current_prefix}{item}/ [Permission Denied]\n")
                else:
                    entries.append(f"{current_prefix}{item}\n")
            
            return "".join(entries)
        
        # Start with the root directory
        tree = f"./\n{build_tree(dir_path)}"
        return tree.rstrip()  # Remove trailing newline
        
    except Exception as e:
        return f"Error: {e}"
    
def delete_file(file_path: str) -> bool:
    """
    Delete a file in the memory.

    Args:
        file_path: The path to the file.

    Returns:
        True if the file was deleted successfully, False otherwise.
    """
    try:
        os.remove(file_path)
        return True
    except Exception:
        return False
    
def go_to_link(link_string: str) -> str:
    """
    Go to a link in the memory and return the content of the note Y. A link in a note X to a note Y, with the
    path path/to/note/Y.md, is structured like this:
    [[path/to/note/Y]]

    Args:
        link_string: The link to go to.

    Returns:
        The content of the note Y, or an error message if the link cannot be accessed.
    """
    try:
        # Handle Obsidian-style links: [[path/to/note]] -> path/to/note.md
        if link_string.startswith("[[") and link_string.endswith("]]"):
            file_path = link_string[2:-2]  # Remove [[ and ]]
            if not file_path.endswith('.md'):
                file_path += '.md'
        else:
            file_path = link_string
            
        # Ensure the file path is properly resolved
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found"
        
        if not os.path.isfile(file_path):
            return f"Error: {file_path} is not a file"
            
        with open(file_path, "r") as f:
            return f.read()
    except PermissionError:
        return f"Error: Permission denied accessing {link_string}"
    except Exception as e:
        return f"Error: {e}"

def check_if_file_exists(file_path: str) -> bool:
    """
    Check if a file exists in the given filepath.
    
    Args:
        file_path: The path to the file.
        
    Returns:
        True if the file exists and is a file, False otherwise.
    """
    try:
        return os.path.exists(file_path) and os.path.isfile(file_path)
    except (OSError, TypeError, ValueError):
        return False

def check_if_dir_exists(dir_path: str) -> bool:
    """
    Check if a directory exists in the given filepath.
    
    Args:
        dir_path: The path to the directory.
        
    Returns:
        True if the directory exists and is a directory, False otherwise.
    """
    try:
        return os.path.exists(dir_path) and os.path.isdir(dir_path)
    except (OSError, TypeError, ValueError):
        return False