"""
File operation tools for the agent.
All file operations are sandboxed to a workspace directory.
"""

from langchain_core.tools import tool
from ..registry import registry
from pathlib import Path
import os

# Configure workspace directory - can be overridden via environment variable
WORKSPACE_DIR = Path(os.getenv("TOOLS_WORKSPACE_DIR", "/tmp/agent_workspace"))


def _validate_path(file_path: str) -> Path:
    """
    Validate that the path is within the allowed workspace directory.
    Prevents directory traversal attacks and unauthorized file access.
    """
    try:
        full_path = (WORKSPACE_DIR / file_path).resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid path: {e}")
    
    # Ensure it's within workspace
    if not str(full_path).startswith(str(WORKSPACE_DIR.resolve())):
        raise ValueError(f"Access denied: Path must be within workspace directory")
    
    return full_path


@registry.register('files')
@tool
def read_file(file_path: str) -> str:
    """
    Read the contents of a file from the workspace.
    Only files within the configured workspace directory can be accessed.
    """
    try:
        safe_path = _validate_path(file_path)
        if not safe_path.exists():
            return f"Error: File not found: {file_path}"
        if not safe_path.is_file():
            return f"Error: Not a file: {file_path}"
        return safe_path.read_text()
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@registry.register('files')
@tool
def list_directory(dir_path: str = ".") -> str:
    """
    List the contents of a directory within the workspace.
    Only directories within the configured workspace directory can be accessed.
    """
    try:
        safe_path = _validate_path(dir_path)
        if not safe_path.exists():
            return f"Error: Directory not found: {dir_path}"
        if not safe_path.is_dir():
            return f"Error: Not a directory: {dir_path}"
        
        items = []
        for item in safe_path.iterdir():
            item_type = "dir" if item.is_dir() else "file"
            items.append(f"{item.name} ({item_type})")
        
        return "\n".join(sorted(items)) if items else "Empty directory"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


@registry.register('files')
@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file within the workspace.
    Only files within the configured workspace directory can be written.
    """
    try:
        safe_path = _validate_path(file_path)
        # Create parent directories if they don't exist
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content)
        return f"File written successfully: {file_path}"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"
