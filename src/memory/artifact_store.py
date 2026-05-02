"""
Artifact Store — file-system-based persistent memory with dependency graph.

Directory layout:
    memory/
      schema/   {table_name}.json, _index.json
      metrics/  {metric_name}.json, _index.json
      queries/  {query_id}.json, _index.json
      insights/ {insight_id}.json, _index.json
      sessions/ {session_id}.json, {session_id}_scratchpad.json, _index.json
      _graph.json
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .models import (
    ARTIFACT_TYPE_MAP,
    ArtifactStatus,
    ArtifactType,
    BaseArtifact,
    EdgeType,
    GraphEdge,
    IndexEntry,
    SchemaArtifact,
    Scratchpad,
    artifact_from_dict,
)

# Map ArtifactType → subdirectory name
_DIR_MAP: Dict[ArtifactType, str] = {
    ArtifactType.SCHEMA:  "schema",
    ArtifactType.METRIC:  "metrics",
    ArtifactType.INSIGHT: "insights",
    ArtifactType.CONTEXT: "context",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactStore:
    """
    File-system based artifact store with dependency graph, versioning,
    indexing, and drift detection.

    When enable_rag=True, artifacts are also embedded into a FAISS vector
    store for semantic search (used in SAM+RAG mode).
    """

    def __init__(self, base_path: str = "memory", enable_rag: bool = False):
        self.base = Path(base_path)
        self.rag = None
        if enable_rag:
            from .rag_baseline import RAGBaseline
            self.rag = RAGBaseline(base_path=base_path)
        self._ensure_dirs()

    # ------------------------------------------------------------------
    # Directory setup
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        """Create the directory tree if it doesn't exist."""
        for subdir in _DIR_MAP.values():
            (self.base / subdir).mkdir(parents=True, exist_ok=True)
        # Ensure graph exists
        if not self._graph_path.exists():
            self._atomic_write(self._graph_path, {"edges": []})

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _type_dir(self, art_type: ArtifactType) -> Path:
        return self.base / _DIR_MAP[art_type]

    def _artifact_path(self, art_type: ArtifactType, art_id: str) -> Path:
        return self._type_dir(art_type) / f"{art_id}.json"

    def _index_path(self, art_type: ArtifactType) -> Path:
        return self._type_dir(art_type) / "_index.json"

    @property
    def _graph_path(self) -> Path:
        return self.base / "_graph.json"

    def _scratchpad_path(self, session_id: str) -> Path:
        """Per-session scratchpad stored alongside session artifacts."""
        return self.base / "sessions" / f"{session_id}_scratchpad.json"

    # ------------------------------------------------------------------
    # Atomic file I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_write(path: Path, data: Any) -> None:
        """Write JSON atomically via temp file + rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            os.unlink(tmp)
            raise

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Index operations
    # ------------------------------------------------------------------

    def _read_index(self, art_type: ArtifactType) -> List[Dict]:
        data = self._read_json(self._index_path(art_type))
        if data is None:
            return []
        return data.get("artifacts", [])

    def _write_index(self, art_type: ArtifactType, entries: List[Dict]) -> None:
        self._atomic_write(self._index_path(art_type), {"artifacts": entries})

    def _upsert_index(self, artifact: BaseArtifact) -> None:
        """Add or update an artifact's entry in its type index."""
        entries = self._read_index(artifact.type)
        name = self._artifact_display_name(artifact)
        summary = self._artifact_summary_preview(artifact)
        new_entry = {
            "id": artifact.id,
            "name": name,
            "status": artifact.status.value,
            "version": artifact.version,
            "updated_at": str(artifact.updated_at),
            "summary": summary,
        }
        # Replace existing or append
        entries = [e for e in entries if e["id"] != artifact.id]
        entries.append(new_entry)
        self._write_index(artifact.type, entries)

    @staticmethod
    def _artifact_summary_preview(artifact: BaseArtifact) -> str:
        """Short summary (≤120 chars) for index display."""
        if hasattr(artifact, "formula") and artifact.formula:
            return str(artifact.formula)[:120]
        if hasattr(artifact, "finding") and artifact.finding:
            return str(artifact.finding)[:120]
        if hasattr(artifact, "description") and artifact.description:
            return str(artifact.description)[:120]
        if hasattr(artifact, "sql") and artifact.sql:
            return str(artifact.sql)[:120]
        return ""

    def _remove_from_index(self, art_type: ArtifactType, art_id: str) -> None:
        entries = self._read_index(art_type)
        entries = [e for e in entries if e["id"] != art_id]
        self._write_index(art_type, entries)

    @staticmethod
    def _artifact_display_name(artifact: BaseArtifact) -> str:
        """Human-readable name for index display."""
        if hasattr(artifact, "table_name"):
            return artifact.table_name
        if hasattr(artifact, "name"):
            return artifact.name
        if hasattr(artifact, "summary"):
            return artifact.summary[:60]
        if hasattr(artifact, "finding"):
            return artifact.finding[:60]
        if hasattr(artifact, "sql"):
            return artifact.sql[:60]
        return artifact.id

    # ------------------------------------------------------------------
    # Graph operations
    # ------------------------------------------------------------------

    def _read_graph(self) -> List[Dict]:
        data = self._read_json(self._graph_path) or {"edges": []}
        return data.get("edges", [])

    def _write_graph(self, edges: List[Dict]) -> None:
        self._atomic_write(self._graph_path, {"edges": edges})

    def _add_edges(self, new_edges: List[GraphEdge]) -> None:
        """Add edges to the graph, deduplicating."""
        edges = self._read_graph()
        existing = {(e["from_id"], e["to_id"], e["type"]) for e in edges}
        for edge in new_edges:
            key = (edge.from_id, edge.to_id, edge.type.value)
            if key not in existing:
                edges.append(edge.model_dump())
                existing.add(key)
        self._write_graph(edges)

    def _remove_edges_for(self, art_id: str) -> None:
        """Remove all edges involving an artifact."""
        edges = self._read_graph()
        edges = [e for e in edges if e["from_id"] != art_id and e["to_id"] != art_id]
        self._write_graph(edges)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_artifacts(
        self,
        art_type: ArtifactType,
        status: Optional[ArtifactStatus] = None,
    ) -> List[Dict]:
        """Return index entries for an artifact type, optionally filtered by status."""
        entries = self._read_index(art_type)
        if status is not None:
            entries = [e for e in entries if e.get("status") == status.value]
        return entries

    def read_artifact(self, art_id: str, art_type: Optional[ArtifactType] = None) -> Optional[BaseArtifact]:
        """
        Read a full artifact by ID.

        If art_type is not provided, searches all type directories.
        """
        if art_type is not None:
            data = self._read_json(self._artifact_path(art_type, art_id))
            if data is None:
                return None
            artifact = artifact_from_dict(data)
        else:
            artifact = self._find_artifact(art_id)
            if artifact is None:
                return None

        return artifact

    def _find_artifact(self, art_id: str) -> Optional[BaseArtifact]:
        """Search all type dirs for an artifact by ID."""
        for art_type in ArtifactType:
            path = self._artifact_path(art_type, art_id)
            if path.exists():
                data = self._read_json(path)
                if data:
                    return artifact_from_dict(data)
        return None

    def write_artifact(self, artifact: BaseArtifact) -> BaseArtifact:
        """
        Write an artifact to disk, update index and graph.

        Auto-creates dependency edges from artifact.dependencies.
        Returns the artifact (with any modifications).
        """
        artifact.updated_at = _now()

        # Write the artifact file
        self._atomic_write(
            self._artifact_path(artifact.type, artifact.id),
            artifact.model_dump(),
        )

        # Update index
        self._upsert_index(artifact)

        # Sync to FAISS if RAG is enabled (SAM+RAG mode)
        if self.rag is not None:
            try:
                self.rag.write_artifact(artifact)
            except Exception as e:
                logger.warning(f"Failed to sync artifact {artifact.id} to FAISS: {e}")

        # Update graph: add structural edges from dependencies
        if artifact.dependencies:
            edges = [
                GraphEdge(from_id=dep, to_id=artifact.id, type=EdgeType.STRUCTURAL)
                for dep in artifact.dependencies
            ]
            self._add_edges(edges)

            # Also update the dependents list of upstream artifacts
            for dep_id in artifact.dependencies:
                dep_artifact = self._find_artifact(dep_id)
                if dep_artifact and artifact.id not in dep_artifact.dependents:
                    dep_artifact.dependents.append(artifact.id)
                    dep_artifact.updated_at = _now()
                    self._atomic_write(
                        self._artifact_path(dep_artifact.type, dep_artifact.id),
                        dep_artifact.model_dump(),
                    )

        return artifact

    def update_artifact(
        self,
        art_id: str,
        payload_changes: Dict[str, Any],
        reason: str = "",
    ) -> Optional[BaseArtifact]:
        """
        Version-bump and update an artifact.

        1. Read current artifact
        2. Copy to {id}_v{version}.json
        3. Increment version, apply changes
        4. Update index and graph
        """
        artifact = self.read_artifact(art_id)
        if artifact is None:
            return None

        # Save prior version
        old_version_id = f"{artifact.id}_v{artifact.version}"
        self._atomic_write(
            self._artifact_path(artifact.type, old_version_id),
            artifact.model_dump(),
        )
        artifact.history.append(old_version_id)

        # Apply changes
        for key, value in payload_changes.items():
            if hasattr(artifact, key):
                setattr(artifact, key, value)

        artifact.version += 1
        artifact.updated_at = _now()
        if reason:
            artifact.tags["last_update_reason"] = reason

        # Write updated artifact
        self._atomic_write(
            self._artifact_path(artifact.type, artifact.id),
            artifact.model_dump(),
        )
        self._upsert_index(artifact)

        return artifact

    def deprecate_artifact(
        self,
        art_id: str,
        reason: str = "",
        replaced_by: Optional[str] = None,
    ) -> Optional[BaseArtifact]:
        """
        Mark an artifact as deprecated.
        Propagates drift warnings to dependents.
        """
        artifact = self.read_artifact(art_id)
        if artifact is None:
            return None

        artifact.status = ArtifactStatus.DEPRECATED
        artifact.updated_at = _now()
        if reason:
            artifact.tags["deprecation_reason"] = reason
        if replaced_by:
            artifact.tags["replaced_by"] = replaced_by

        self._atomic_write(
            self._artifact_path(artifact.type, artifact.id),
            artifact.model_dump(),
        )
        self._upsert_index(artifact)

        return artifact

    def delete_artifact(self, art_id: str, art_type: Optional[ArtifactType] = None) -> bool:
        """Delete an artifact, its index entry, and graph edges."""
        if art_type is None:
            artifact = self._find_artifact(art_id)
            if artifact is None:
                return False
            art_type = artifact.type

        path = self._artifact_path(art_type, art_id)
        if not path.exists():
            return False

        path.unlink()
        self._remove_from_index(art_type, art_id)
        self._remove_edges_for(art_id)
        return True

    # ------------------------------------------------------------------
    # Dependency graph traversal
    # ------------------------------------------------------------------

    def get_dependencies(
        self,
        art_id: str,
        direction: str = "both",
    ) -> Dict[str, List[Dict]]:
        """
        Traverse the dependency graph.

        direction: "up" (what this depends on), "down" (what depends on this), "both"
        """
        edges = self._read_graph()
        result: Dict[str, List[Dict]] = {"upstream": [], "downstream": []}

        if direction in ("up", "both"):
            result["upstream"] = [e for e in edges if e["to_id"] == art_id]
        if direction in ("down", "both"):
            result["downstream"] = [e for e in edges if e["from_id"] == art_id]

        return result

    def link_artifacts(
        self,
        from_id: str,
        to_id: str,
        relationship: str,
    ) -> bool:
        """Add a semantic edge between artifacts."""
        try:
            edge_type = EdgeType(relationship)
        except ValueError:
            logger.warning(f"Unknown edge type: {relationship}")
            return False

        self._add_edges([GraphEdge(from_id=from_id, to_id=to_id, type=edge_type)])
        return True

    # ------------------------------------------------------------------
    # Scratchpad (per-session)
    # ------------------------------------------------------------------

    def read_scratchpad(self, session_id: str) -> Scratchpad:
        """Read the scratchpad for a specific session."""
        data = self._read_json(self._scratchpad_path(session_id))
        if data is None:
            return Scratchpad()
        return Scratchpad(**data)

    def write_scratchpad(self, session_id: str, scratchpad: Scratchpad) -> None:
        """Write the scratchpad for a specific session."""
        self._atomic_write(self._scratchpad_path(session_id), scratchpad.model_dump())

    def clear_scratchpad(self, session_id: str) -> None:
        """Clear the scratchpad for a specific session."""
        self._atomic_write(self._scratchpad_path(session_id), Scratchpad().model_dump())


    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Delete all artifacts, indexes, graph, and scratchpad. For testing."""
        import shutil
        if self.base.exists():
            shutil.rmtree(self.base)
        self._ensure_dirs()
