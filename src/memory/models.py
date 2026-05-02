"""
Artifact models for the structured persistent memory system.

Defines the 3 thesis artifact types:
  SchemaArtifact, MetricArtifact, InsightArtifact

Plus GenericContext (for RAG), the base model, enums, dependency graph,
and scratchpad structures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ArtifactType(str, Enum):
    SCHEMA  = "schema"
    METRIC  = "metric"
    INSIGHT = "insight"
    CONTEXT = "context"


class ArtifactStatus(str, Enum):
    ACTIVE     = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class Confidence(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class EdgeType(str, Enum):
    """Relationship types between artifacts in the dependency graph."""
    STRUCTURAL   = "structural"     # Auto-detected from SQL / definitions
    REFINES      = "refines"        # Agent-declared: new artifact improves old
    CONTRADICTS  = "contradicts"    # Agent-declared: findings conflict
    VALIDATES    = "validates"      # Agent-declared: confirms prior finding


# ---------------------------------------------------------------------------
# Base Artifact
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _artifact_id() -> str:
    return str(uuid.uuid4())[:8]


class BaseArtifact(BaseModel):
    """Common fields shared by all artifact types."""
    id: str = Field(default_factory=_artifact_id)
    type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    session_id: str = ""
    version: int = 1
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    history: List[str] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)

class GenericContext(BaseArtifact):
    """Generic context artifact for unstructured text."""
    type: ArtifactType = ArtifactType.CONTEXT
    text: str

# ---------------------------------------------------------------------------
# Schema Artifact
# ---------------------------------------------------------------------------

class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    default: Optional[str] = None


class ForeignKey(BaseModel):
    column: str
    references_table: str
    references_column: str


class SchemaArtifact(BaseArtifact):
    """Represents a database table's schema, introspected from the live DB."""
    type: ArtifactType = ArtifactType.SCHEMA
    table_name: str
    columns: List[ColumnInfo] = Field(default_factory=list)
    foreign_keys: List[ForeignKey] = Field(default_factory=list)
    row_count_estimate: Optional[int] = None


# ---------------------------------------------------------------------------
# Metric Artifact
# ---------------------------------------------------------------------------

class MetricArtifact(BaseArtifact):
    """Agent-defined business metric."""
    type: ArtifactType = ArtifactType.METRIC
    name: str
    description: str
    formula: str
    unit: Optional[str] = None





# ---------------------------------------------------------------------------
# Insight Artifact
# ---------------------------------------------------------------------------

class InsightArtifact(BaseArtifact):
    """Agent-created analytical finding backed by metrics or other artifacts."""
    type: ArtifactType = ArtifactType.INSIGHT
    finding: str
    supporting_artifact_ids: List[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM


# ---------------------------------------------------------------------------
# Dependency Graph Edge
# ---------------------------------------------------------------------------

class GraphEdge(BaseModel):
    """A single edge in the artifact dependency graph."""
    from_id: str
    to_id: str
    type: EdgeType = EdgeType.STRUCTURAL


# ---------------------------------------------------------------------------
# Scratchpad
# ---------------------------------------------------------------------------

class Scratchpad(BaseModel):
    """Session-scoped working memory injected into every prompt."""
    goal: str = ""
    key_schema: str = ""
    assumptions: str = ""
    open_questions: str = ""
    relevant_artifacts: str = ""


# ---------------------------------------------------------------------------
# Index Entry (lightweight summary for _index.json)
# ---------------------------------------------------------------------------

class IndexEntry(BaseModel):
    """Lightweight record stored in per-type _index.json files."""
    id: str
    name: str = ""
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    version: int = 1
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Type registry — maps ArtifactType to its Pydantic class
# ---------------------------------------------------------------------------

ARTIFACT_TYPE_MAP: Dict[ArtifactType, type] = {
    ArtifactType.SCHEMA:  SchemaArtifact,
    ArtifactType.METRIC:  MetricArtifact,
    ArtifactType.INSIGHT: InsightArtifact,
    ArtifactType.CONTEXT: GenericContext,
}


def artifact_from_dict(data: Dict[str, Any]) -> BaseArtifact:
    """Deserialize a JSON dict into the correct artifact subclass."""
    art_type = ArtifactType(data["type"])
    cls = ARTIFACT_TYPE_MAP[art_type]
    return cls(**data)
