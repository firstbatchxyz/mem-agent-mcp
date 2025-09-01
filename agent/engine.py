import builtins
import importlib
import logging
import os
import sys
import traceback
import types
import pickle
import subprocess
import base64

from agent.settings import SANDBOX_TIMEOUT

# Configure a logger for the sandbox (in real use, configure handlers/level as needed)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or DEBUG for more verbosity


def _run_user_code(
    code: str,
    allow_installs: bool,
    allowed_path: str,
    blacklist: list,
    available_functions: dict,
    log: bool = False,
) -> tuple[dict, str]:
    """
    Execute code under sandboxed conditions (limited file access, optional installs,
    and blacklisting) and return the resulting locals and an error message.
    """
    try:
        # Optional: apply working directory and file access restriction
        if allowed_path:
            allowed = os.path.abspath(allowed_path)
            try:
                os.chdir(allowed)  # Change working dir to the allowed_path
            except Exception as e:
                # If we cannot chdir, log but continue (the open wrapper will still enforce path)
                logger.warning(
                    "Could not change working directory to %s: %s", allowed, e
                )
            # Wrap builtins.open to restrict file access
            orig_open = builtins.open

            def secure_open(file, *args, **kwargs):
                """Open that restricts file access to allowed_path."""
                # If file is a file object or path-like, get its string path
                path = (
                    file if isinstance(file, str) else getattr(file, "name", str(file))
                )
                full_path = os.path.abspath(path if path is not None else "")
                if not full_path.startswith(allowed):
                    raise PermissionError(
                        f"Access to '{full_path}' is denied by sandbox."
                    )
                return orig_open(file, *args, **kwargs)

            builtins.open = secure_open

            # Optionally, restrict other file-related functions (remove, rename, etc.) similarly
            # We'll patch a couple of common ones as an example:
            orig_remove = os.remove

            def secure_remove(path, *args, **kwargs):
                full_path = os.path.abspath(path)
                if not full_path.startswith(allowed):
                    raise PermissionError(
                        f"Removal of '{full_path}' is denied by sandbox."
                    )
                return orig_remove(path, *args, **kwargs)

            os.remove = secure_remove

            orig_rename = os.rename

            def secure_rename(src, dst, *args, **kwargs):
                full_src = os.path.abspath(src)
                full_dst = os.path.abspath(dst)
                if not full_src.startswith(allowed) or not full_dst.startswith(allowed):
                    raise PermissionError(
                        "Rename operation outside allowed path is denied by sandbox."
                    )
                return orig_rename(src, dst, *args, **kwargs)

            os.rename = secure_rename

        # Apply blacklist restrictions by removing or disabling blacklisted builtins or attributes
        if blacklist:
            for name in blacklist:
                # If the name has a dot, like "os.system", handle module attributes
                if "." in name:
                    mod_name, attr_name = name.split(".", 1)
                    try:
                        mod_obj = importlib.import_module(mod_name)
                    except ImportError:
                        mod_obj = None
                    # If module is imported in sandbox, remove the attribute
                    if mod_obj and hasattr(mod_obj, attr_name):
                        try:
                            setattr(
                                mod_obj, attr_name, None
                            )  # simple way: nullify the attribute
                        except Exception:
                            pass  # if we cannot set it, ignore (might be read-only)
                else:
                    # It's a built-in or global name; remove from builtins if present
                    if name in builtins.__dict__:
                        builtins.__dict__[name] = (
                            None  # or we could del, but setting None prevents use
                        )
            # Additionally, we can ensure __builtins__ in the exec env doesn't contain them (handled below in exec)

        # If allowed, handle package installations inside sandbox (in case code itself triggers ImportError)
        if allow_installs:
            # We will install missing imports on the fly during execution if an ImportError occurs.
            # One approach: wrap __import__ to catch failed imports and pip install.
            orig_import = builtins.__import__

            def custom_import(name, globals=None, locals=None, fromlist=(), level=0):
                try:
                    return orig_import(name, globals, locals, fromlist, level)
                except ImportError as e:
                    pkg = name.split(".")[0]
                    logger.info(
                        "Sandbox: attempting to install missing package '%s'", pkg
                    )
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", pkg],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception as inst_err:
                        # If installation fails, re-raise the original ImportError
                        logger.error(
                            "Sandbox: failed to install package %s: %s", pkg, inst_err
                        )
                        raise e
                    # Retry the import after installation
                    return orig_import(name, globals, locals, fromlist, level)

            builtins.__import__ = custom_import

        # Prepare an isolated execution namespace. We use an empty globals dict with a fresh builtins.
        exec_globals = {"__builtins__": builtins.__dict__}

        # Add any provided functions to the execution environment
        if available_functions:
            exec_globals.update(available_functions)

        exec_locals = {}  # local variables will be collected here

        error_msg = None
        try:
            exec(code, exec_globals, exec_locals)  # Execute the user's code
        except Exception as e:
            # Catch any exception and format it
            tb = traceback.format_exc()
            error_msg = f"Exception in sandboxed code:\n{tb}"
            if log:
                logger.error("Sandbox: code raised an exception: %s", e)
        except SystemExit as e:
            # Handle sys.exit calls (which raise SystemExit)
            code_val = e.code if isinstance(e.code, int) or e.code else 0
            if code_val != 0:
                error_msg = f"Sandboxed code called sys.exit({code_val})"
                if log:
                    logger.warning(
                        "Sandbox: code exited with non-zero status %s", code_val
                    )
            # For sys.exit(0), we treat it as normal termination (no error)

        # Clean up any blacklisted or internal entries in locals
        exec_locals.pop("__builtins__", None)

        # Collect only picklable locals for returning
        safe_locals = {}
        for var, val in exec_locals.items():
            try:
                pickle.dumps(val)  # test picklability
                safe_locals[var] = val
            except Exception:
                safe_locals[var] = repr(val)  # fallback: use string representation

        if log:
            logger.info("Sandbox execution finished")

        return safe_locals, error_msg

    except Exception as e:
        # Catch any unhandled exceptions in the worker process
        if log:
            logger.error(
                "Unhandled exception in sandbox worker: %s", traceback.format_exc()
            )
        return None, f"Sandbox worker error: {str(e)}"


def execute_sandboxed_code(
    code: str,
    timeout: int = SANDBOX_TIMEOUT,
    allow_installs: bool = False,
    requirements_path: str = None,
    allowed_path: str = None,
    blacklist: list = None,
    available_functions: dict = None,
    import_module: str = None,
    log: bool = False,
) -> tuple[dict, str]:
    """
    Execute the given Python code string in a sandboxed subprocess with specified restrictions.

    Parameters:
        code (str): The Python code to execute.
        timeout (int): Maximum execution time in seconds for the sandboxed code (default 10 seconds).
        allow_installs (bool): If True, allow installing missing packages via pip (default False).
        requirements_path (str): Path to a requirements.txt file to install before execution.
        allowed_path (str): Directory path that the code is allowed to access for file I/O.
                            File operations outside this path will be blocked. If None, no extra file restrictions are applied.
        blacklist (list): List of names (builtins or module attributes) that are disallowed in the code.
                          If the code uses any of these, it will be prevented or result in an error.
        available_functions (dict): Dictionary of functions to make available in the sandboxed environment.
                                   The keys are the function names, and the values are the function objects.
        import_module (str): Name of a Python module to import and make all its functions available in the sandbox.

    Returns:
        (dict, str): A tuple containing the dictionary of local variables from the executed code (or None on failure),
                     and an error message (str) if an error/exception occurred, or None if execution was successful.
    """
    # Step 1: If package installs are allowed, handle requirements and prepare environment
    if requirements_path:
        if os.path.isfile(requirements_path):
            logger.info(
                "Installing packages from requirements file: %s", requirements_path
            )
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", requirements_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                logger.error(
                    "Failed to install requirements from %s: %s", requirements_path, e
                )
                # If requirements fail to install, we can choose to abort or continue. Here, abort execution.
                return None, f"Failed to install requirements: {e}"
        else:
            logger.error("Requirements file %s not found.", requirements_path)
            return None, f"Requirements file not found: {requirements_path}"

    # If a module name is provided, import it and add its functions to available_functions
    if isinstance(available_functions, str) and not import_module:
        import_module = available_functions
        available_functions = None

    if import_module:
        try:
            module = importlib.import_module(import_module)
            if available_functions is None:
                available_functions = {}
            for name in dir(module):
                if not name.startswith("_"):
                    attr = getattr(module, name)
                    if callable(attr):
                        available_functions[name] = attr
        except ImportError as e:
            logger.error(f"Failed to import module {import_module}: {e}")
            return None, f"Failed to import module {import_module}: {e}"

    # Step 2: Execute the code in a separate Python subprocess
    params = {
        "code": code,
        "allow_installs": allow_installs,
        "allowed_path": allowed_path,
        "blacklist": blacklist or [],
        "available_functions": available_functions or {},
        "log": log,
    }

    env = os.environ.copy()
    env["SANDBOX_PARAMS"] = base64.b64encode(pickle.dumps(params)).decode()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "agent.engine"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Sandboxed code exceeded time limit of %d seconds; terminating.", timeout
        )
        return None, f"TimeoutError: Code execution exceeded {timeout} seconds."

    if result.returncode != 0:
        return None, result.stderr.decode().strip()

    try:
        local_vars, error_msg = pickle.loads(result.stdout)
    except Exception as e:
        return None, f"Failed to decode sandbox output: {e}"

    if error_msg is None:
        error_msg = ""

    return local_vars, error_msg


def _subprocess_entry() -> None:
    """Entry point for sandbox subprocess."""
    params_b64 = os.environ.get("SANDBOX_PARAMS")
    if not params_b64:
        sys.exit(1)
    params = pickle.loads(base64.b64decode(params_b64))
    locals_dict, error = _run_user_code(
        params["code"],
        params.get("allow_installs", False),
        params.get("allowed_path"),
        params.get("blacklist", []),
        params.get("available_functions", {}),
        params.get("log", False),
    )
    sys.stdout.buffer.write(pickle.dumps((locals_dict, error)))


if __name__ == "__main__":
    _subprocess_entry()
