"""
Memory tools package — structured artifact graph tools.

Auto-registers all memory tools on import.
"""

from .memory_tools import (
    list_artifacts,
    read_artifact,
    get_dependencies,
    save_definition,
    save_insight,
    update_artifact,
    deprecate_artifact,
    link_artifacts,
    run_query,
    set_artifact_store,
)

__all__ = [
    "list_artifacts",
    "read_artifact",
    "get_dependencies",
    "save_definition",
    "save_insight",
    "update_artifact",
    "deprecate_artifact",
    "link_artifacts",
    "run_query",
    "set_artifact_store",
]
