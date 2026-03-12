"""
NSIA Analysis History — SQLite-backed storage for AI analysis results.

Stores each AI analysis run with metadata for:
- Tracking how findings change over time
- Comparing current vs. prior analyses
- Building a compliance audit trail
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "analysis_history.db")


def _get_conn() -> sqlite3.Connection:
    """Get a connection, creating the table if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            source_page TEXT,
            filename TEXT,
            input_summary TEXT,
            result TEXT NOT NULL,
            red_flags INTEGER DEFAULT 0,
            yellow_flags INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analyses_agent ON analyses(agent_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp)
    """)
    conn.commit()
    return conn


def save_analysis(
    agent_id: str,
    agent_name: str,
    result: str,
    source_page: str = "",
    filename: str = "",
    input_summary: str = "",
    metadata: Optional[dict] = None,
) -> int:
    """Save an analysis result. Returns the row ID."""
    red_flags = result.count("\U0001f534")  # red circle emoji
    yellow_flags = result.count("\U0001f7e1")  # yellow circle emoji

    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO analyses
           (timestamp, agent_id, agent_name, source_page, filename,
            input_summary, result, red_flags, yellow_flags, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(),
            agent_id,
            agent_name,
            source_page,
            filename,
            input_summary[:500] if input_summary else "",
            result,
            red_flags,
            yellow_flags,
            json.dumps(metadata) if metadata else None,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_recent_analyses(limit: int = 20, agent_id: str = "") -> list[dict]:
    """Get recent analyses, optionally filtered by agent."""
    conn = _get_conn()
    if agent_id:
        rows = conn.execute(
            "SELECT * FROM analyses WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analysis_by_id(analysis_id: int) -> Optional[dict]:
    """Get a single analysis by ID."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_analysis_stats() -> dict:
    """Get summary statistics about stored analyses."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    by_agent = conn.execute(
        "SELECT agent_name, COUNT(*) as count FROM analyses GROUP BY agent_name ORDER BY count DESC"
    ).fetchall()
    total_red = conn.execute("SELECT SUM(red_flags) FROM analyses").fetchone()[0] or 0
    total_yellow = conn.execute("SELECT SUM(yellow_flags) FROM analyses").fetchone()[0] or 0
    latest = conn.execute(
        "SELECT timestamp FROM analyses ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    conn.close()

    return {
        "total_analyses": total,
        "by_agent": [dict(r) for r in by_agent],
        "total_red_flags": total_red,
        "total_yellow_flags": total_yellow,
        "latest_timestamp": latest[0] if latest else None,
    }


def compare_analyses(agent_id: str, limit: int = 2) -> list[dict]:
    """Get the most recent analyses for an agent to enable comparison."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM analyses WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
        (agent_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_analysis(analysis_id: int) -> bool:
    """Delete an analysis by ID."""
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
