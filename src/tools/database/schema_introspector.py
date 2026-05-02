"""
Schema Introspector — Phase 4

Syncs the Postgres database schema into the ArtifactStore as SchemaArtifacts.
"""

import psycopg
from loguru import logger
from src.config.settings import settings
from src.memory.models import SchemaArtifact, ColumnInfo, ArtifactType
from src.memory.artifact_store import ArtifactStore

def sync_schema(store: ArtifactStore, conn_str: str | None = None) -> dict:
    """
    Introspect the Postgres schema and sync it to the ArtifactStore.
    
    Returns a summary of changes.
    """
    conn_str = conn_str or settings.database_url
    
    # Introspect tables and columns from information_schema
    # Exclude system tables
    query = """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    
    schemas = {}
    
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                for row in cur.fetchall():
                    tbl, col, dtype = row
                    if tbl not in schemas:
                        schemas[tbl] = []
                    schemas[tbl].append(ColumnInfo(name=col, data_type=dtype))
    except Exception as e:
        logger.error(f"Failed to introspect schema: {e}")
        return {"error": str(e)}
        
    created = 0
    updated = 0
    deprecated = 0
    
    # Get current schema artifacts
    existing_entries = store.list_artifacts(ArtifactType.SCHEMA)
    existing_ids = {e["id"] for e in existing_entries}
    
    # Process found schemas
    for tbl, columns in schemas.items():
        # Clean up table name to use as ID
        # In a real system, we'd prefix with schema name or connection id, 
        # but for the single-DB thesis scope, just the table name works.
        schema_id = tbl.lower()
        
        if schema_id in existing_ids:
            # Check for changes
            old_art = store.read_artifact(schema_id, ArtifactType.SCHEMA)
            if old_art and isinstance(old_art, SchemaArtifact):
                old_cols = {c.name: c.data_type for c in old_art.columns}
                new_cols = {c.name: c.data_type for c in columns}
                
                if old_cols != new_cols:
                    logger.info(f"Schema changed for {tbl}, updating artifact")
                    # Update and drift detect
                    store.update_artifact(
                        schema_id, 
                        {"columns": [c.model_dump() for c in columns]}, 
                        reason="Schema introspection change detected"
                    )
                    updated += 1
            existing_ids.remove(schema_id)
        else:
            # Create new
            art = SchemaArtifact(
                id=schema_id,
                table_name=tbl,
                columns=columns,
                session_id="system_sync"
            )
            store.write_artifact(art)
            created += 1
            
    # Any remaining existing_ids represent dropped tables
    for dropped_id in existing_ids:
        logger.warning(f"Table dropped: {dropped_id}, deprecating artifact")
        store.deprecate_artifact(dropped_id, reason="Table dropped from database")
        deprecated += 1
        
    return {
        "status": "success",
        "tables_found": len(schemas),
        "created": created,
        "updated": updated,
        "deprecated": deprecated
    }
