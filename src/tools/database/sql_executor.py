"""
SQL executor utility — runs queries against PostgreSQL.

Extracted from the old query_tool.py for reuse by the new run_query tool.
"""

import re
import psycopg
from loguru import logger
from ...config.settings import settings


def execute_sql(
    sql: str,
    conn_str: str | None = None,
    max_rows: int = 1000,
    timeout: int = 30,
) -> dict:
    """
    Execute a SQL query and return structured results.

    Returns:
        {
            "success": True/False,
            "columns": [...],
            "rows": [[...], ...],
            "row_count": int,
            "formatted": "human-readable string",
            "execution_time_ms": float,
            "error": None or str,
        }
    """
    conn_str = conn_str or settings.database_url
    import time
    start = time.time()

    # Auto-add LIMIT for unbounded SELECTs
    q_stripped = sql.strip().rstrip(";").strip()
    q_upper = q_stripped.upper()
    if q_upper.startswith("SELECT") and "LIMIT" not in q_upper:
        sql = q_stripped + f" LIMIT {max_rows}"
    else:
        sql = q_stripped
    
    logger.debug(f"Executing SQL: {sql[:200]}...")

    try:
        with psycopg.connect(conn_str, options=f"-c statement_timeout={timeout * 1000}") as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                elapsed_ms = (time.time() - start) * 1000

                if cur.description is None:
                    return {
                        "success": True,
                        "columns": [],
                        "rows": [],
                        "row_count": cur.rowcount,
                        "formatted": f"✅ Query executed. Rows affected: {cur.rowcount}",
                        "execution_time_ms": elapsed_ms,
                        "error": None,
                    }

                columns = [desc[0] for desc in cur.description]
                rows = [list(row) for row in cur.fetchmany(max_rows)]
                elapsed_ms = (time.time() - start) * 1000

                # Format for display
                if not rows:
                    formatted = f"Query returned 0 rows.\nColumns: {', '.join(columns)}"
                else:
                    lines = [" | ".join(columns), "-" * max(len(" | ".join(columns)), 10)]
                    for row in rows:
                        lines.append(" | ".join(str(v) for v in row))
                    lines.append(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''} returned)")
                    formatted = "\n".join(lines)

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "formatted": formatted,
                    "execution_time_ms": elapsed_ms,
                    "error": None,
                }

    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        logger.error(f"SQL execution error: {e}")
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "formatted": f"❌ SQL error: {e}",
            "execution_time_ms": elapsed_ms,
            "error": str(e),
        }


def parse_table_references(sql: str) -> list[str]:
    """
    Extract table names from a SQL query using simple regex.
    (Good enough for thesis scope; no full SQL parser needed.)
    """
    # Match FROM table, JOIN table patterns
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for m in matches:
        lower = m.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result
