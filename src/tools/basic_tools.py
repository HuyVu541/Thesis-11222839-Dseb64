"""
Agent tools — main interface.

Tools are organized by category and registered automatically.
Memory tools are loaded based on MEMORY_MODE setting (rag, or sam).
"""

from typing import List
from langchain_core.tools import BaseTool

# Import to register tools (non-memory categories always loaded)
from . import math
from . import files
from .registry import registry

# Conditionally import memory tools based on mode
from ..config.settings import settings

if settings.memory_mode == "rag":
    from .memory import rag_tools  # noqa: F401 — registers memory_rag tools
    _MEMORY_CATEGORY = "memory_rag"
elif settings.memory_mode == "sam":
    from .memory import sam_rag_tools  # noqa: F401 — registers memory_sam_rag tools
    _MEMORY_CATEGORY = "memory_sam_rag"
else:
    from . import memory  # noqa: F401 — registers memory (SPM) tools
    _MEMORY_CATEGORY = "memory"


def get_tools(categories: List[str] = None) -> List[BaseTool]:
    """Get tools by category. When no categories specified, returns all
    registered tools (only one memory module is ever imported at startup)."""
    return registry.get_tools(categories)


def list_available_tools() -> dict:
    """List all available tools organized by category."""
    result = {}
    for category in registry.list_categories():
        result[category] = registry.list_tools(category)
    return result