"""
Obsidian Agent package.
"""

try:
    from .agent import Agent
    from .engine import execute_sandboxed_code
    
    __all__ = [
        "Agent",
        "execute_sandboxed_code",
    ]
except ImportError:
    # If some modules can't be imported, just make the package importable
    __all__ = []
