"""
RAG Baseline Memory Backend.

This provides the semantic search baseline to compare against the
Structured Persistent Memory (SPM) architecture in the evaluation.
It chunks artifacts and embeds them using FAISS and Google's embedding model.
"""

from typing import List, Dict, Any, Optional
import os
import json
from pathlib import Path
from loguru import logger
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from ..config.settings import settings
from .models import BaseArtifact

class RAGBaseline:
    """FAISS-based RAG memory for evaluation comparison."""

    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.memory_base_path) / "rag_baseline"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_path / "faiss_index"

        # Use models/gemini-embedding-001 as per previous conversation fix
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

        self.vectorstore: Optional[FAISS] = None
        self._load_or_create_index()

    def _load_or_create_index(self):
        if (self.index_path / "index.faiss").exists():
            try:
                self.vectorstore = FAISS.load_local(
                    folder_path=str(self.index_path),
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Loaded existing RAG index from {self.index_path}")
            except Exception as e:
                logger.error(f"Failed to load RAG index: {e}. Recreating...")
                self._create_empty_index()
        else:
            self._create_empty_index()

    def _create_empty_index(self):
        # Create an empty vector store with a dummy doc to initialize dimensions
        dummy_doc = Document(page_content="initialization", metadata={"dummy": True})
        self.vectorstore = FAISS.from_documents([dummy_doc], self.embeddings)
        # Immediately delete the dummy doc
        docs_to_delete = [
            doc_id for doc_id, doc in self.vectorstore.docstore._dict.items()
            if doc.metadata.get("dummy")
        ]
        if docs_to_delete:
            self.vectorstore.delete(docs_to_delete)
        self._save_index()
        logger.info("Initialized empty RAG index.")

    def _save_index(self):
        if self.vectorstore:
            self.vectorstore.save_local(str(self.index_path))

    def _format_artifact_text(self, artifact: BaseArtifact) -> str:
        """Convert artifact into a rich text chunk for embedding."""
        lines = [
            f"ID: {artifact.id}",
            f"Type: {artifact.type.value if hasattr(artifact, 'type') else type(artifact).__name__}",
            f"Version: {artifact.version}",
            f"Created: {artifact.created_at}",
            f"Updated: {artifact.updated_at}",
        ]
        
        # Add all fields dynamically
        for k, v in artifact.model_dump(exclude={"history", "drift_warning"}).items():
            if k not in ("id", "type", "version", "created_at", "updated_at", "session_id", "tags") and v:
                lines.append(f"{k.capitalize()}: {v}")
                
        return "\n".join(lines)

    def write_artifact(self, artifact: BaseArtifact):
        """Add or update an artifact in the RAG index."""
        try:
            # 1. Check if it already exists and delete old chunks
            old_docs = [
                doc_id for doc_id, doc in self.vectorstore.docstore._dict.items()
                if doc.metadata.get("artifact_id") == artifact.id
            ]
            if old_docs:
                self.vectorstore.delete(old_docs)

            # 2. Add new document
            text = self._format_artifact_text(artifact)
            doc = Document(
                page_content=text,
                metadata={
                    "artifact_id": artifact.id,
                    "type": artifact.type.value if hasattr(artifact, 'type') else type(artifact).__name__,
                    "version": artifact.version,
                    "session_id": artifact.session_id,
                    "created_at": str(artifact.created_at),
                    "updated_at": str(artifact.updated_at),
                }
            )
            self.vectorstore.add_documents([doc])
            self._save_index()
            
        except Exception as e:
            logger.error(f"Error saving artifact to RAG: {e}")

    def search(self, query: str, k: int = 5, filter_dict: dict = None) -> List[Dict[str, Any]]:
        """Semantic search over artifacts."""
        if not self.vectorstore:
            return []

        try:
            results = self.vectorstore.similarity_search_with_score(
                query, k=k, filter=filter_dict
            )
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "id": doc.metadata.get("artifact_id"),
                    "type": doc.metadata.get("type"),
                    "score": float(score),
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })
            return formatted_results
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return []

    def reset(self):
        """Clear the entire index (for tests)."""
        import shutil
        if self.base_path.exists():
            shutil.rmtree(self.base_path)
        self.base_path.mkdir(parents=True)
        self._create_empty_index()
