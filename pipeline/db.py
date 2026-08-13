"""
pipeline/db.py — SQLite database layer.
Runs schema.sql then schema_whatsapp_migration.sql at startup.
All tables helpers live here.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import DB_PATH, ROOT

_local = threading.local()

SCHEMA_SQL = ROOT / "config" / "schema.sql"
SCHEMA_WA_SQL = ROOT / "config" / "schema_whatsapp_migration.sql"


def get_conn() -> sqlite3.Connection:
    """Return a per-thread connection (create if needed)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_conn()

    # Main schema — use executescript which handles comments and multi-statements
    conn.executescript(SCHEMA_SQL.read_text())

    # WhatsApp migration — ALTER TABLE statements fail if columns already exist.
    # Execute each statement individually so we can swallow duplicate-column errors.
    import re as _re
    migration_text = SCHEMA_WA_SQL.read_text()
    # Strip comment lines before splitting on semicolons
    stripped = _re.sub(r"--[^\n]*", "", migration_text)
    statements = [s.strip() for s in stripped.split(";") if s.strip()]
    for stmt in statements:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            err = str(e).lower()
            if "duplicate column" in err or "already exists" in err:
                pass  # migration already applied
            else:
                raise
    conn.commit()



# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------

def upsert_session(session_id: str, channel: str = "web",
                   wa_id: str = None, profile_name: str = None) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO chat_sessions (session_id, channel, wa_id, profile_name, last_active_at, last_inbound_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            last_active_at = CURRENT_TIMESTAMP,
            last_inbound_at = CURRENT_TIMESTAMP
        """,
        (session_id, channel, wa_id, profile_name),
    )
    conn.commit()


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()


def update_session_field(session_id: str, **kwargs) -> None:
    if not kwargs:
        return
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    conn.execute(
        f"UPDATE chat_sessions SET {sets} WHERE session_id = ?",
        (*kwargs.values(), session_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Message history helpers
# --------------------------------------------------------------------------

def log_message(
    session_id: str,
    sender: str,
    message_text: str,
    redaction_applied: str = None,
    action_taken: str = None,
    assessed_level: int = None,
    retrieval_score: float = None,
    evidence_verdict: str = None,
    grounding_chunks: str = None,
    placeholder_hit: int = 0,
    latency_ms: int = None,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO message_history
            (session_id, sender, message_text, redaction_applied, action_taken,
             assessed_level, retrieval_score, evidence_verdict, grounding_chunks,
             placeholder_hit, latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, sender, message_text, redaction_applied, action_taken,
         assessed_level, retrieval_score, evidence_verdict, grounding_chunks,
         placeholder_hit, latency_ms),
    )
    conn.commit()
    return cur.lastrowid


def get_message_history(session_id: str, limit: int = 20) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """
        SELECT sender, message_text, timestamp FROM message_history
        WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()[::-1]  # chronological order


# --------------------------------------------------------------------------
# Escalation ticket helpers
# --------------------------------------------------------------------------

def create_ticket(
    session_id: str,
    level: int,
    trigger_type: str,
    is_event_not_question: bool,
    primary_factors: str,
    routed_to_label: str,
    routed_to_email: str,
    reason_summary: str,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO escalation_tickets
            (session_id, level, trigger_type, is_event_not_question,
             primary_factors, routed_to_label, routed_to_email, reason_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, level, trigger_type, int(is_event_not_question),
         primary_factors, routed_to_label, routed_to_email, reason_summary),
    )
    conn.commit()
    return cur.lastrowid


def update_ticket_send(ticket_id: int, status: str, error: str = None,
                       customer_informed: int = 0, attempts: int = 1) -> None:
    conn = get_conn()
    conn.execute(
        """
        UPDATE escalation_tickets
        SET send_status = ?, send_error = ?, customer_informed = ?,
            send_attempts = ?
        WHERE ticket_id = ?
        """,
        (status, error, customer_informed, attempts, ticket_id),
    )
    conn.commit()


def get_existing_ticket(session_id: str, level: int) -> Optional[sqlite3.Row]:
    """Return the most recent ticket for this session+level (deduplication)."""
    conn = get_conn()
    return conn.execute(
        """
        SELECT * FROM escalation_tickets
        WHERE session_id = ? AND level = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (session_id, level),
    ).fetchone()


# --------------------------------------------------------------------------
# Knowledge gap helpers
# --------------------------------------------------------------------------

def log_knowledge_gap(
    session_id: str,
    query: str,
    similarity_score: float,
    evidence_verdict: str,
    nearest_chunk: str,
    placeholder_blocked: int = 0,
    topic_cluster: str = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO knowledge_gaps
            (session_id, unanswered_query, similarity_score, evidence_verdict,
             nearest_chunk, placeholder_blocked, topic_cluster)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, query, similarity_score, evidence_verdict,
         nearest_chunk, placeholder_blocked, topic_cluster),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Guardrail violation helpers
# --------------------------------------------------------------------------

def log_violation(
    session_id: str,
    violation_type: str,
    detail: str = None,
    action_taken: str = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO guardrail_violations
            (session_id, violation_type, detail, action_taken)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, violation_type, detail, action_taken),
    )
    conn.commit()


# --------------------------------------------------------------------------
# WhatsApp deduplication helpers
# --------------------------------------------------------------------------

def is_message_processed(message_sid: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM processed_messages WHERE provider_message_id = ?",
        (message_sid,),
    ).fetchone()
    return row is not None


def mark_message_processed(message_sid: str, session_id: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO processed_messages (provider_message_id, session_id) VALUES (?, ?)",
        (message_sid, session_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Admin API helpers
# --------------------------------------------------------------------------

def get_tickets_for_admin(limit: int = 100) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """
        SELECT ticket_id, session_id, level, trigger_type, reason_summary,
               send_status, send_attempts, customer_informed, created_at
        FROM escalation_tickets
        ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_top_knowledge_gaps(limit: int = 5) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """
        SELECT topic_cluster, COUNT(*) AS hits,
               AVG(similarity_score) AS avg_score,
               SUM(placeholder_blocked) AS placeholder_hits
        FROM knowledge_gaps
        WHERE topic_cluster IS NOT NULL
        GROUP BY topic_cluster ORDER BY hits DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_placeholder_gaps(limit: int = 20) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """
        SELECT unanswered_query, nearest_chunk, timestamp
        FROM knowledge_gaps WHERE placeholder_blocked = 1
        ORDER BY timestamp DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_violations_by_type() -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """
        SELECT violation_type, COUNT(*) AS count,
               MAX(timestamp) AS last_seen
        FROM guardrail_violations
        GROUP BY violation_type ORDER BY count DESC
        """,
    ).fetchall()


def get_metrics() -> dict:
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM message_history WHERE sender = 'CUSTOMER'"
    ).fetchone()[0] or 1

    contained = conn.execute(
        "SELECT COUNT(*) FROM message_history WHERE action_taken IN ('ANSWER','CONSOLE','MENU','CLARIFY')"
    ).fetchone()[0]

    escalated = conn.execute(
        "SELECT COUNT(*) FROM message_history WHERE action_taken IN ('ESCALATE','SAFETY_HANDOFF')"
    ).fetchone()[0]

    action_dist = conn.execute(
        """
        SELECT action_taken, COUNT(*) AS cnt
        FROM message_history WHERE action_taken IS NOT NULL
        GROUP BY action_taken ORDER BY cnt DESC
        """
    ).fetchall()

    return {
        "total_messages": total,
        "containment_rate": round(contained / total * 100, 1),
        "escalation_rate": round(escalated / total * 100, 1),
        "action_distribution": [dict(r) for r in action_dist],
    }
