"""
Histórico de Execuções e Tarefas usando SQLite.
Armazenado em %APPDATA%/WinToolbox/history.db
"""
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List
from wintoolbox.core.settings import get_settings_dir

def get_history_db_path() -> Path:
    return get_settings_dir() / "history.db"

def _init_db():
    p = get_history_db_path()
    with sqlite3.connect(p) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                items_total INTEGER DEFAULT 0,
                items_success INTEGER DEFAULT 0,
                items_failed INTEGER DEFAULT 0,
                duration_sec REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                message TEXT
            )
        """)
        conn.commit()

def record_job(
    tool_id: str,
    items_total: int,
    items_success: int,
    items_failed: int,
    duration_sec: float,
    status: str,
    message: str = ""
):
    """Registra uma execução concluída no histórico."""
    _init_db()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(get_history_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO job_history (tool_id, timestamp, items_total, items_success, items_failed, duration_sec, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tool_id, now_str, items_total, items_success, items_failed, duration_sec, status, message)
        )
        conn.commit()

def get_recent_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """Recupera os trabalhos executados mais recentemente."""
    _init_db()
    with sqlite3.connect(get_history_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM job_history ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

def clear_history():
    """Limpa todo o histórico de tarefas."""
    _init_db()
    with sqlite3.connect(get_history_db_path()) as conn:
        conn.execute("DELETE FROM job_history")
        conn.commit()
