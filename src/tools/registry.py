"""
Tool Registry - Central management for agent tools.

This module provides a registry pattern for tools, making it easy to:
- Register new tools
- Enable/disable tools by category
- Manage tool availability
"""

from typing import List, Dict, Optional, Set
from langchain_core.tools import BaseTool
from loguru import logger


class ToolRegistry:
    """Central registry for managing agent tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, Set[str]] = {}
    
    def register(self, category: str, name: Optional[str] = None):
        """
        Decorator to register a tool.
        
        Args:
            category: Tool category (e.g., 'math', 'files', 'web')
            name: Optional custom name (defaults to function name)
            
        Example:
            @registry.register('math')
            @tool
            def calculator(expr: str) -> str:
                return str(eval(expr))
        """
        def wrapper(tool: BaseTool):
            tool_name = name or tool.name
            full_name = f"{category}.{tool_name}"
            
            self._tools[full_name] = tool
            
            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(full_name)
            
            logger.debug(f"Registered tool: {full_name}")
            return tool
        
        return wrapper
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a specific tool by name."""
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools as a dictionary {full_name: tool}."""
        return self._tools.copy()

    def get_tools(self, categories: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Get tools by category.
        
        Args:
            categories: List of categories to include (None = all)
            
        Returns:
            List of tool instances
            
        Example:
            # Get all tools
            all_tools = registry.get_tools()
            
            # Get only math and file tools
            tools = registry.get_tools(['math', 'files'])
        """
        if categories is None:
            return list(self._tools.values())
        
        tools = []
        for category in categories:
            if category in self._categories:
                for tool_name in self._categories[category]:
                    tools.append(self._tools[tool_name])
        
        return tools
    
    def list_categories(self) -> List[str]:
        """Get all registered categories."""
        return list(self._categories.keys())
    
    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """
        List all tool names, optionally filtered by category.
        
        Args:
            category: Filter by category (None = all)
            
        Returns:
            List of tool names
        """
        if category is None:
            return list(self._tools.keys())
        
        if category in self._categories:
            return list(self._categories[category])
        
        return []


# Global registry instance
registry = ToolRegistry()
