"""
SAM+RAG Memory Tools — combines all SAM structural tools with semantic search.

This module re-exports all SAM tools from memory_tools.py and adds
search_memory backed by the embedded FAISS index in ArtifactStore.
"""

from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ..registry import registry

# Re-export all SAM tools so they register under "memory_sam_rag"
from .memory_tools import (
    _get_store,
    set_artifact_store,
    list_artifacts as _list_artifacts,
    read_artifact as _read_artifact,
    get_dependencies as _get_dependencies,
    save_definition as _save_definition,
    save_insight as _save_insight,
    update_artifact as _update_artifact,
    deprecate_artifact as _deprecate_artifact,
    link_artifacts as _link_artifacts,
    run_query as _run_query,
)

# Re-register SAM tools under the "memory_sam_rag" category
for _tool_fn in [
    _list_artifacts,
    _read_artifact,
    _get_dependencies,
    _save_definition,
    _save_insight,
    _update_artifact,
    _deprecate_artifact,
    _link_artifacts,
    _run_query,
]:
    registry.register("memory_sam_rag")(_tool_fn)


# ===================================================================
# SEMANTIC SEARCH (backed by FAISS in the ArtifactStore)
# ===================================================================

@registry.register("memory_sam_rag")
@tool
def search_memory(
    query: str,
    k: int = 5,
    artifact_type: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """Search memory for relevant artifacts using semantic similarity.

    Uses FAISS vector embeddings to find artifacts whose content is
    semantically similar to the query. Returns the most relevant matches
    with their IDs, types, and content previews.

    Args:
        query: The search query (natural language)
        k: Number of results to return (default: 5)
        artifact_type: Optional filter by type: schema, metric, query, insight
    """
    store = _get_store()

    if not hasattr(store, 'rag') or store.rag is None:
        return "❌ Semantic search is not available in this mode."

    filter_dict = None
    if artifact_type:
        filter_dict = {"type": artifact_type}

    results = store.rag.search(query, k=k, filter_dict=filter_dict)

    if not results:
        return f"No results found for: '{query}'"

    lines = [f"🔍 Search results for '{query}' ({len(results)} matches):"]
    for r in results:
        score = r.get("score", 0)
        art_id = r.get("id", "?")
        art_type = r.get("type", "?")
        content = r.get("content", "")
        lines.append(f"\n  📄 {art_id} (type={art_type}, score={score:.3f})")
        lines.append(f"     {content}")

    return "\n".join(lines)
