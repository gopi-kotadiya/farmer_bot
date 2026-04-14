import os
import sqlite3
from typing import List, Optional

DB_PATH = "db/kisanbot.db"

# PDF: mausam / mandi / pest
ALLOWED_ALERT_TYPES = frozenset({"mausam", "mandi", "pest"})


def get_connection():
    """Create a database connection."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema (farmers, conversation_history, alerts)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            session_id TEXT,
            name TEXT,
            location TEXT,
            crops TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # PDF Table 3: alerts (alert log)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_telegram_id ON alerts(telegram_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts(sent_at)"
    )

    # PDF farmers table: email for alerts — add if DB already existed without column
    cursor.execute("PRAGMA table_info(farmers)")
    farmer_cols = {row[1] for row in cursor.fetchall()}
    if "email" not in farmer_cols:
        cursor.execute("ALTER TABLE farmers ADD COLUMN email TEXT")

    conn.commit()
    conn.close()


def log_alert(telegram_id: str, alert_type: str, message: str) -> Optional[int]:
    """
    Save one alert row (mausam / mandi / pest). Returns new row id or None on error.
    """
    tid = (telegram_id or "").strip()
    if not tid:
        return None
    atype = (alert_type or "").strip().lower()
    if atype not in ALLOWED_ALERT_TYPES:
        return None
    msg = (message or "").strip()
    if not msg:
        return None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alerts (telegram_id, alert_type, message)
            VALUES (?, ?, ?)
            """,
            (tid, atype, msg),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return int(row_id) if row_id is not None else None
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def get_alerts_for_user(telegram_id: str, limit: int = 50) -> List[dict]:
    """Recent alerts for a farmer (newest first)."""
    tid = (telegram_id or "").strip()
    if not tid:
        return []
    lim = max(1, min(int(limit), 200))
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, telegram_id, alert_type, message, sent_at
            FROM alerts
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tid, lim),
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
