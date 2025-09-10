"""
ChatGPT to mem-agent converter package.
"""

from .types import *
from .parser import ChatGPTParser
from .converter import MemoryConverter
from .connector import ChatGPTHistoryConnector

# Convenience wrapper functions
def parse_export(export_path: str):
    """Parse ChatGPT export using default options."""
    parser = ChatGPTParser()
    return parser.parse_export(export_path)

def convert_export(export_path: str, memory_path: str, max_conversations: int = None):
    """Convert ChatGPT export to mem-agent format."""
    converter = MemoryConverter(memory_path)
    return converter.convert_export(export_path, max_conversations)