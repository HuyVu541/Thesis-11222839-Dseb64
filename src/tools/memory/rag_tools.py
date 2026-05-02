"""
RAG Baseline Tools for Evaluation.

Pure RAG mode: 2 agent-facing tools (search_memory, run_query).
Memory is populated automatically by the system — each conversation turn
and query result is auto-embedded into the FAISS vector store.
"""

from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ..registry import registry
from ...memory.rag_baseline import RAGBaseline


# Global RAG store wired at startup if RAG mode is active
_rag_store = None


def set_rag_store(store_instance: RAGBaseline):
    """Wire the global RAGBaseline for tools."""
    global _rag_store
    _rag_store = store_instance


def _get_rag():
    global _rag_store
    if _rag_store is None:
        _rag_store = RAGBaseline()
    return _rag_store


# ===================================================================
# RAG TOOLS (search_memory + run_query only)
# ===================================================================

@registry.register("memory_rag")
@tool
def search_memory(
    query: str,
    k: int = 5,
    config: RunnableConfig = None,
) -> str:
    """Search memory for relevant past work using semantic similarity.

    Returns the most relevant results from all past conversations,
    query results, and saved context.

    Args:
        query: The search query (natural language)
        k: Number of results to return (default: 5)
    """
    rag = _get_rag()
    results = rag.search(query, k=k)

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


@registry.register("memory_rag")
@tool
def run_query(
    sql: str,
    config: RunnableConfig = None,
) -> str:
    """Execute a SQL query against the project database.

    Args:
        sql: The SQL query to execute
    """
    from ..database.sql_executor import execute_sql

    result = execute_sql(sql)
    return result["formatted"]