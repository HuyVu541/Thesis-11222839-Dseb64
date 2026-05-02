"""
Database manager for the BI Agent backend.

Simplified for single-project scope: sessions, system prompts, and eval runs.
"""

import psycopg
from ..config.settings import settings
from .models import SessionCreate, SessionResponse
from typing import List, Optional
from loguru import logger


class DatabaseManager:
    def __init__(self):
        self.conn_str = settings.database_url
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization - only connect when actually needed."""
        if not self._initialized:
            self.init_db()
            self._initialized = True

    def _get_conn(self):
        return psycopg.connect(self.conn_str, autocommit=True)

    def init_db(self):
        """Ensure required tables exist."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS prompts (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        content TEXT NOT NULL,
                        version TEXT DEFAULT '1.0',
                        is_active BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS eval_runs (
                        id SERIAL PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        memory_mode TEXT NOT NULL,
                        scenario TEXT NOT NULL,
                        total_turns INTEGER,
                        total_latency_s REAL,
                        total_input_tokens INTEGER,
                        total_output_tokens INTEGER,
                        total_tokens INTEGER,
                        ex_passed INTEGER,
                        ex_total INTEGER,
                        ex_score REAL,
                        all_passed BOOLEAN,
                        qualitative_analysis TEXT,
                        turns_json JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Backwards-compatible schema evolution: add memory_mode column
                # to prompts so we can store different prompts for different
                # memory backends (e.g., SPM vs RAG).
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name = 'prompts' AND column_name = 'memory_mode'
                        ) THEN
                            ALTER TABLE prompts ADD COLUMN memory_mode TEXT;
                        END IF;
                    END$$;
                """)
                logger.info("Database tables initialized")

    # ===== Session CRUD =====

    def create_session(self, session: SessionCreate) -> SessionResponse:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (id, title) VALUES (%s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title "
                    "RETURNING id, title, created_at",
                    (session.id, session.title)
                )
                row = cur.fetchone()

                return SessionResponse(id=row[0], title=row[1], created_at=row[2])

    def get_sessions(self) -> List[SessionResponse]:
        self._ensure_initialized()
        sessions = []
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC")
                for row in cur.fetchall():
                    sessions.append(SessionResponse(id=row[0], title=row[1], created_at=row[2]))
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                return cur.rowcount > 0

    # ===== Prompt Management =====

    def get_prompts(self) -> List[dict]:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, description, content, version, is_active, created_at FROM prompts ORDER BY created_at DESC")
                return [{"id": r[0], "name": r[1], "description": r[2], "content": r[3],
                         "version": r[4], "is_active": r[5], "created_at": r[6]} for r in cur.fetchall()]

    def get_prompt(self, prompt_id: str) -> Optional[dict]:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, description, content, version, is_active, created_at FROM prompts WHERE id = %s", (prompt_id,))
                r = cur.fetchone()
                if not r:
                    return None
                return {"id": r[0], "name": r[1], "description": r[2], "content": r[3],
                        "version": r[4], "is_active": r[5], "created_at": r[6]}

    def get_active_prompt(self) -> Optional[dict]:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, content, version, is_active, created_at, memory_mode "
                    "FROM prompts WHERE is_active = TRUE ORDER BY created_at DESC LIMIT 1"
                )
                r = cur.fetchone()
                if not r:
                    return None
                return {
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "content": r[3],
                    "version": r[4],
                    "is_active": r[5],
                    "created_at": r[6],
                    "memory_mode": r[7],
                }

    def get_prompt_for_mode(self, memory_mode: str) -> Optional[dict]:
        """Get the active prompt for a given memory mode (e.g., 'spm', 'rag').

        Falls back to the global active prompt if no mode-specific prompt exists.
        """
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, content, version, is_active, created_at, memory_mode "
                    "FROM prompts WHERE is_active = TRUE AND memory_mode = %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (memory_mode,),
                )
                r = cur.fetchone()
                if not r:
                    return self.get_active_prompt()
                return {
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "content": r[3],
                    "version": r[4],
                    "is_active": r[5],
                    "created_at": r[6],
                    "memory_mode": r[7],
                }

    def set_active_prompt(self, prompt_id: str) -> bool:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE prompts SET is_active = FALSE WHERE is_active = TRUE")
                cur.execute("UPDATE prompts SET is_active = TRUE WHERE id = %s", (prompt_id,))
                return cur.rowcount > 0

    def update_prompt_content(self, prompt_id: str, content: str) -> Optional[dict]:
        self._ensure_initialized()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE prompts SET content = %s WHERE id = %s "
                    "RETURNING id, name, description, content, version, is_active, created_at",
                    (content, prompt_id)
                )
                r = cur.fetchone()
                if not r:
                    return None
                return {"id": r[0], "name": r[1], "description": r[2], "content": r[3],
                        "version": r[4], "is_active": r[5], "created_at": r[6]}


    # ===== Eval Runs =====

    def save_eval_run(self, data: dict) -> int:
        """Insert an evaluation run and return its ID."""
        self._ensure_initialized()
        import json as _json
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO eval_runs "
                    "(run_id, memory_mode, scenario, total_turns, total_latency_s, "
                    " total_input_tokens, total_output_tokens, total_tokens, "
                    " ex_passed, ex_total, ex_score, all_passed, qualitative_analysis, turns_json) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (
                        data["run_id"],
                        data["memory_mode"],
                        data["scenario"],
                        data.get("total_turns", 0),
                        data.get("total_latency_s", 0.0),
                        data.get("total_input_tokens", 0),
                        data.get("total_output_tokens", 0),
                        data.get("total_tokens", 0),
                        data.get("ex_passed", 0),
                        data.get("ex_total", 0),
                        data.get("ex_score", 0.0),
                        data.get("all_passed", False),
                        data.get("qualitative_analysis", ""),
                        _json.dumps(data.get("turns", []), default=str),
                    ),
                )
                row = cur.fetchone()
                return row[0] if row else -1


db_manager = DatabaseManager()
