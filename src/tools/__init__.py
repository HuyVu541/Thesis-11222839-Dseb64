"""
Tools package for AI agent.

Tools are organized by category:
- math: Mathematical operations (calculator, etc.)
- files: File system operations (read, write, list)

Use the registry to get tools:
    from tools import get_tools, registry
    
    # Get all tools
    all_tools = get_tools()
    
    # Get specific categories
    math_tools = get_tools(['math'])
    
    # List available tools
    from tools import list_available_tools
    print(list_available_tools())
"""

from .basic_tools import get_tools, list_available_tools
from .registry import registry

__all__ = ['get_tools', 'list_available_tools', 'registry']