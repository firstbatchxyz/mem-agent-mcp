import os
import shutil

import black

from agent.settings import (
    SYSTEM_PROMPT_PATH,
    FILE_SIZE_LIMIT,
    DIR_SIZE_LIMIT,
    MEMORY_SIZE_LIMIT,
    MEMORY_PATH,
)


def load_system_prompt() -> str:
    """
    Load the system prompt from the file.

    Returns:
        The system prompt as a string.
    """
    try:
        with open(SYSTEM_PROMPT_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"System prompt file not found at {SYSTEM_PROMPT_PATH}")


def check_file_size_limit(file_path: str) -> bool:
    """
    Check if the file size limit is respected.
    """
    return os.path.getsize(file_path) <= FILE_SIZE_LIMIT


def check_dir_size_limit(dir_path: str) -> bool:
    """
    Check if the directory size limit is respected.
    """
    return os.path.getsize(dir_path) <= DIR_SIZE_LIMIT


def check_memory_size_limit() -> bool:
    """
    Check if the memory size limit is respected.
    """
    current_working_dir = os.getcwd()
    return os.path.getsize(current_working_dir) <= MEMORY_SIZE_LIMIT


def check_size_limits(file_or_dir_path: str) -> bool:
    """
    Check if the size limits are respected.
    """
    if file_or_dir_path == "":
        return check_memory_size_limit()
    elif os.path.isdir(file_or_dir_path):
        return check_dir_size_limit(file_or_dir_path) and check_memory_size_limit()
    elif os.path.isfile(file_or_dir_path):
        parent_dir = os.path.dirname(file_or_dir_path)
        if not parent_dir == "":
            return (
                check_file_size_limit(file_or_dir_path)
                and check_dir_size_limit(parent_dir)
                and check_memory_size_limit()
            )
        else:
            return check_file_size_limit(file_or_dir_path) and check_memory_size_limit()
    else:
        return False


def create_memory_if_not_exists(path: str = MEMORY_PATH):
    """
    Create the memory if it doesn't exist.

    Args:
        path: The path to create. Defaults to MEMORY_PATH.

    Returns:
        None
    """
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating memory directory at {path}: {e}")


def delete_memory(path: str = MEMORY_PATH) -> None:
    """
    Delete the memory.

    Args:
        path: The path to delete. Defaults to MEMORY_PATH.
    """
    if os.path.exists(path):
        shutil.rmtree(path)


def _format_python_code_with_black(code: str) -> str:
    """
    Format Python code using Black formatter.
    
    Args:
        code: The Python code to format
        
    Returns:
        The formatted Python code, or original code if formatting fails
    """
    if not code.strip():
        return code
        
    try:
        # For incomplete code fragments, wrap them in a function to make them valid Python
        # This helps Black parse and format them correctly
        lines = code.strip().split('\n')
        
        # Check if code looks like complete statements or just expressions/fragments
        needs_wrapping = True
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith(('def ', 'class ', 'import ', 'from ')) or 
                stripped.startswith(('if ', 'for ', 'while ', 'try:', 'with ')) or
                '=' in stripped or stripped.startswith(('print(', 'return '))):
                needs_wrapping = False
                break
        
        if needs_wrapping:
            # Wrap in a function to make it valid Python for Black
            wrapped_code = f"def temp_function():\n" + "\n".join(f"    {line}" for line in lines)
            
            try:
                formatted_wrapped = black.format_str(
                    wrapped_code,
                    mode=black.FileMode(
                        line_length=88,
                        string_normalization=True,
                        is_pyi=False,
                    )
                )
                # Extract the formatted content back out, removing the wrapper
                formatted_lines = formatted_wrapped.split('\n')[1:]  # Skip "def temp_function():"
                formatted_code = '\n'.join(line[4:] if line.startswith('    ') else line 
                                         for line in formatted_lines if line.strip()).strip()
                return formatted_code
            except:
                # If wrapping fails, try formatting as-is
                pass
        
        # Try formatting the code as-is
        formatted_code = black.format_str(
            code, 
            mode=black.FileMode(
                line_length=88,
                string_normalization=True,
                is_pyi=False,
            )
        )
        return formatted_code
        
    except (black.InvalidInput, ValueError, SyntaxError, Exception) as e:
        # If Black fails to format (e.g., invalid syntax), return original code
        # This ensures we don't break the training pipeline
        return code


def extract_python_code(response: str) -> str:
    """
    Extract the python code from the response and format it with Black.

    Args:
        response: The response from the model.

    Returns:
        The formatted python code from the response.
    """
    if "<python>" in response and "</python>" in response:
        response = response.split("<python>")[1].split("</python>")[0]
        if "```" in response:
            code = response.split("```")[1].split("```")[0]
        else:
            code = response
        
        # Format the extracted code with Black
        return _format_python_code_with_black(code)
    else:
        return ""


def extract_reply(response: str) -> str:
    """
    Extract the reply from the response.
    """
    if "<reply>" in response and "</reply>" in response:
        return response.split("<reply>")[1].split("</reply>")[0]
    else:
        return ""


def extract_thoughts(response: str) -> str:
    """
    Extract the thoughts from the response.
    """
    if "<think>" in response and "</think>" in response:
        return response.split("<think>")[1].split("</think>")[0]
    else:
        return ""


def format_results(results: dict, error_msg: str = "") -> str:
    """
    Format the results into a string.
    """
    return (
        "<result>\n(" + str(results) + ", {" + error_msg + "})\n</result>"
        if error_msg
        else "<result>\n" + str(results) + "\n</result>"
    )