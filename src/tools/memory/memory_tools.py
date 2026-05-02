"""
Memory tools — SAM agent tools.

Read / Browse:
  list_artifacts, read_artifact, get_dependencies

Mutation:
  save_definition, save_insight, update_artifact, deprecate_artifact, link_artifacts

Query:
  run_query
"""

import json
from typing import Dict, List, Optional, Any, Union
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from loguru import logger

from ..registry import registry

# ---------------------------------------------------------------------------
# Global artifact store — wired at startup by routes.py
# ---------------------------------------------------------------------------
_store = None


def set_artifact_store(store_instance):
    """Wire the global ArtifactStore for all memory tools."""
    global _store
    _store = store_instance


def _get_store():
    global _store
    if _store is None:
        from ...memory.artifact_store import ArtifactStore
        from ...config.settings import settings
        _store = ArtifactStore(base_path=settings.memory_base_path, enable_rag=True)
    return _store


def _log_artifact_interaction(config, artifact_id: str, action: str):
    """Passively log artifact interactions to the SessionArtifact.
    
    (Deprecated since SessionArtifacts were removed to prevent memory clutter)
    """
    pass


# ===================================================================
# READ / BROWSE TOOLS
# ===================================================================

@registry.register("memory")
@tool
def list_artifacts(
    artifact_type: str,
    status: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """List all artifacts of a given type. Returns the index summary.

    Args:
        artifact_type: One of: schema, metric, query, insight
        status: Optional filter: active, deprecated, superseded
    """
    from ...memory.models import ArtifactType, ArtifactStatus

    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        return f"❌ Unknown artifact type: {artifact_type}. Use: schema, metric, query, insight"

    art_status = None
    if status:
        try:
            art_status = ArtifactStatus(status)
        except ValueError:
            return f"❌ Unknown status: {status}. Use: active, deprecated, superseded"

    store = _get_store()
    entries = store.list_artifacts(art_type, status=art_status)

    if not entries:
        return f"No {artifact_type} artifacts found."

    lines = [f"📋 {artifact_type.upper()} artifacts ({len(entries)} total):"]
    for e in entries:
        status_icon = "✅" if e.get("status") == "active" else "⚠️"
        summary = e.get("summary", "")
        line = f"  {status_icon} {e['id']} — {e.get('name', '')} (v{e.get('version', 1)})"
        if summary:
            line += f" | {summary}"
        lines.append(line)
    return "\n".join(lines)


@registry.register("memory")
@tool
def read_artifact(artifact_id: str, config: RunnableConfig = None) -> str:
    """Read a full artifact by its ID.

    For query artifacts, automatically checks for schema drift and
    attaches a warning if the referenced schema has changed.

    Args:
        artifact_id: The unique ID of the artifact to read.
    """
    store = _get_store()
    artifact = store.read_artifact(artifact_id)

    if artifact is None:
        return f"❌ Artifact '{artifact_id}' not found."

    # Format output
    data = artifact.model_dump(exclude_none=True)
    # Clean up datetime serialization
    for key in ("created_at", "updated_at"):
        if key in data:
            data[key] = str(data[key])

    import json
    result = json.dumps(data, indent=2, default=str)

    if hasattr(artifact, "drift_warning") and artifact.drift_warning:
        result = f"⚠️ SCHEMA DRIFT WARNING: {artifact.drift_warning}\n\n{result}"

    _log_artifact_interaction(config, artifact_id, "read")
    return result


@registry.register("memory")
@tool
def get_dependencies(
    artifact_id: str,
    direction: str = "both",
    config: RunnableConfig = None,
) -> str:
    """Traverse the artifact dependency graph.

    Args:
        artifact_id: The artifact whose dependencies to inspect.
        direction: "up" (what this depends on), "down" (what depends on this), "both"
    """
    if direction not in ("up", "down", "both"):
        return "❌ direction must be 'up', 'down', or 'both'"

    store = _get_store()
    deps = store.get_dependencies(artifact_id, direction=direction)

    lines = [f"🔗 Dependencies for '{artifact_id}' (direction={direction}):"]

    if deps["upstream"]:
        lines.append(f"\n  ⬆️ Upstream ({len(deps['upstream'])}):")
        for e in deps["upstream"]:
            lines.append(f"    {e['from_id']} → {artifact_id} ({e['type']})")

    if deps["downstream"]:
        lines.append(f"\n  ⬇️ Downstream ({len(deps['downstream'])}):")
        for e in deps["downstream"]:
            lines.append(f"    {artifact_id} → {e['to_id']} ({e['type']})")

    if not deps["upstream"] and not deps["downstream"]:
        lines.append("  No dependencies found.")

    return "\n".join(lines)



# ===================================================================
# MUTATION TOOLS
# ===================================================================

@registry.register("memory")
@tool
def save_definition(
    name: str,
    description: str,
    formula: str,
    dependencies: Union[List[str], str] = [],
    unit: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """Save a new business metric definition.

    Args:
        name: Short name for the metric (e.g., "Net Revenue")
        description: What the metric measures
        formula: SQL expression or formula
        dependencies: List of artifact IDs this metric depends on (e.g., schema table IDs)
        unit: Optional unit of measurement (e.g., "USD", "%")
    """
    from ...memory.models import MetricArtifact

    session_id = ""
    if config:
        session_id = config.get("metadata", {}).get("session_id", "")

    if isinstance(dependencies, str):
        try:
            dependencies = json.loads(dependencies)
            if not isinstance(dependencies, list):
                dependencies = [str(dependencies)]
        except Exception:
            dependencies = [dependencies]

    if not dependencies:
        warning = "⚠️ No dependencies specified — consider linking to schema artifacts.\n"
    else:
        warning = ""

    # Create ID from name
    metric_id = name.lower().replace(" ", "_").replace("-", "_")

    # Idempotency: check if identical metric already exists
    store = _get_store()
    existing = store.read_artifact(metric_id)
    if existing is not None:
        if (hasattr(existing, 'formula') and existing.formula == formula
                and hasattr(existing, 'description') and existing.description == description):
            return f"ℹ️ Metric '{name}' already exists as '{metric_id}' with the same definition. No changes made."

    metric = MetricArtifact(
        id=metric_id,
        name=name,
        description=description,
        formula=formula,
        unit=unit,
        dependencies=dependencies,
        session_id=session_id,
    )

    store.write_artifact(metric)
    _log_artifact_interaction(config, metric_id, "created")
    return f"{warning}✅ Metric '{name}' saved as '{metric_id}' with {len(dependencies)} dependencies."


@registry.register("memory")
@tool
def save_insight(
    finding: str,
    supporting_artifact_ids: Union[List[str], str] = [],
    confidence: str = "medium",
    config: RunnableConfig = None,
) -> str:
    """Save an analytical insight backed by metrics or other artifacts.

    Args:
        finding: The analytical finding or conclusion
        supporting_artifact_ids: IDs of artifacts (metrics, schemas) that support this insight
        confidence: Confidence level: high, medium, low
    """
    from ...memory.models import InsightArtifact, Confidence

    try:
        conf = Confidence(confidence)
    except ValueError:
        return f"❌ Invalid confidence: {confidence}. Use: high, medium, low"

    session_id = ""
    if config:
        session_id = config.get("metadata", {}).get("session_id", "")

    if isinstance(supporting_artifact_ids, str):
        try:
            supporting_artifact_ids = json.loads(supporting_artifact_ids)
            if not isinstance(supporting_artifact_ids, list):
                supporting_artifact_ids = [str(supporting_artifact_ids)]
        except Exception:
            supporting_artifact_ids = [supporting_artifact_ids]

    insight = InsightArtifact(
        finding=finding,
        supporting_artifact_ids=supporting_artifact_ids,
        confidence=conf,
        dependencies=supporting_artifact_ids,
        session_id=session_id,
    )

    store = _get_store()
    store.write_artifact(insight)
    _log_artifact_interaction(config, insight.id, "created")
    return f"✅ Insight saved as '{insight.id}' with {len(supporting_artifact_ids)} supporting artifacts."


@registry.register("memory")
@tool
def update_artifact(
    artifact_id: str,
    payload_changes: Dict[str, Any],
    reason: str = "",
    config: RunnableConfig = None,
) -> str:
    """Update an existing artifact (version-bump).

    Creates a backup of the prior version and increments the version number.
    Only metrics and insights should be updated; queries are immutable.

    Args:
        artifact_id: ID of the artifact to update
        payload_changes: Dictionary of fields to change (e.g., {"description": "new desc"})
        reason: Reason for the update
    """
    store = _get_store()
    result = store.update_artifact(artifact_id, payload_changes, reason=reason)
    if result is None:
        return f"❌ Artifact '{artifact_id}' not found."
    _log_artifact_interaction(config, artifact_id, "updated")
    return f"✅ Updated '{artifact_id}' to v{result.version}. Reason: {reason or '(none)'}"


@registry.register("memory")
@tool
def deprecate_artifact(
    artifact_id: str,
    reason: str = "",
    replaced_by: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """Mark an artifact as deprecated.

    Propagates drift warnings to all downstream dependents.

    Args:
        artifact_id: ID of the artifact to deprecate
        reason: Why it's being deprecated
        replaced_by: Optional ID of the replacement artifact
    """
    store = _get_store()
    result = store.deprecate_artifact(artifact_id, reason=reason, replaced_by=replaced_by)
    if result is None:
        return f"❌ Artifact '{artifact_id}' not found."
    msg = f"✅ Deprecated '{artifact_id}'."
    if replaced_by:
        msg += f" Replaced by: {replaced_by}"
    if result.dependents:
        msg += f" Drift warnings propagated to {len(result.dependents)} dependents."
    return msg


@registry.register("memory")
@tool
def link_artifacts(
    from_id: str,
    to_id: str,
    relationship: str,
    config: RunnableConfig = None,
) -> str:
    """Add a semantic relationship between two artifacts.

    Args:
        from_id: Source artifact ID
        to_id: Target artifact ID
        relationship: One of: refines, contradicts, validates
    """
    store = _get_store()
    if store.link_artifacts(from_id, to_id, relationship):
        return f"✅ Linked '{from_id}' → '{to_id}' ({relationship})"
    return f"❌ Invalid relationship type: {relationship}. Use: refines, contradicts, validates"



# ===================================================================
# QUERY EXECUTION TOOL
# ===================================================================

@registry.register("memory")
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
