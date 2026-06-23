"""Local User Database: SQLite for scan history and impact stats (Req18-19, NfReq10, SUC5)."""
import logging
import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "recycling.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   TEXT PRIMARY KEY,
            region    TEXT    NOT NULL DEFAULT 'GLOBAL',
            language  TEXT    NOT NULL DEFAULT 'en',
            consent   INTEGER NOT NULL DEFAULT 0,
            created_at TEXT   DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT    NOT NULL,
            item_name    TEXT    NOT NULL,
            material     TEXT    NOT NULL DEFAULT '',
            category     TEXT    NOT NULL DEFAULT '',
            region       TEXT    NOT NULL DEFAULT 'GLOBAL',
            co2_saved    REAL    NOT NULL DEFAULT 0.0,
            energy_saved REAL    NOT NULL DEFAULT 0.0,
            timestamp    TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    conn.commit()
    conn.close()


def ensure_user(user_id: str):
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
    )
    conn.commit()
    conn.close()


def get_user_consent(user_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute("SELECT consent FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return bool(row["consent"]) if row else False


def set_consent(user_id: str, consent: bool):
    ensure_user(user_id)
    conn = _get_conn()
    conn.execute("UPDATE users SET consent = ? WHERE user_id = ?", (int(consent), user_id))
    conn.commit()
    conn.close()


def get_user_region(user_id: str) -> str:
    conn = _get_conn()
    row = conn.execute("SELECT region FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["region"] if row else "GLOBAL"


def set_user_region(user_id: str, region: str):
    ensure_user(user_id)
    conn = _get_conn()
    conn.execute("UPDATE users SET region = ? WHERE user_id = ?", (region, user_id))
    conn.commit()
    conn.close()


def get_user_language(user_id: str) -> str:
    conn = _get_conn()
    row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["language"] if row else "en"


def set_user_language(user_id: str, language: str):
    ensure_user(user_id)
    conn = _get_conn()
    conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
    conn.commit()
    conn.close()


def save_scan(user_id: str, item_name: str, material: str, category: str,
              region: str, co2_saved: float, energy_saved: float):
    """Save only when user has given consent (SUC5 exception 1.A1, NfReq10)."""
    if not get_user_consent(user_id):
        logger.info("Skipping history save — no consent for user %s.", user_id)
        return
    conn = _get_conn()
    conn.execute(
        """INSERT INTO scan_history
           (user_id, item_name, material, category, region, co2_saved, energy_saved)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, item_name, material, category, region, co2_saved, energy_saved),
    )
    conn.commit()
    conn.close()


def get_history(user_id: str) -> Tuple[List[sqlite3.Row], float, float, int]:
    """Return (rows, total_co2, total_energy, total_scans)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM scan_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 100",
        (user_id,),
    ).fetchall()
    totals = conn.execute(
        "SELECT COALESCE(SUM(co2_saved),0), COALESCE(SUM(energy_saved),0), COUNT(*) "
        "FROM scan_history WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return rows, totals[0], totals[1], totals[2]


def clear_history(user_id: str):
    conn = _get_conn()
    conn.execute("DELETE FROM scan_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
