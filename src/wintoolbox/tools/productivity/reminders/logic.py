"""
Lógica pura de persistência e verificação de alarmes e lembretes agendados.
Isolada de bibliotecas de interface visual.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("productivity.reminders")

REPEAT_MODES = {
    "none": "Não repetir (uma vez)",
    "daily": "Diariamente",
    "weekdays": "Dias úteis (Seg a Sex)",
    "weekly": "Semanalmente"
}


def get_reminders_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados de lembretes."""
    app_dir = get_app_dir()
    db_dir = app_dir / "productivity"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "reminders.db"


def init_reminders_db(db_path: Optional[Path] = None) -> Path:
    """Inicializa as tabelas do banco de lembretes."""
    path = db_path or get_reminders_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT DEFAULT '',
                target_time TEXT NOT NULL,
                repeat_mode TEXT DEFAULT 'none',
                is_active INTEGER DEFAULT 1,
                triggered INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rem_active ON reminders(is_active, target_time)")
        conn.commit()

    return path


def add_reminder(
    title: str,
    target_time: datetime,
    message: str = "",
    repeat_mode: str = "none",
    db_path: Optional[Path] = None
) -> int:
    """Agenda um novo lembrete."""
    t = title.strip()
    if not t:
        raise ValueError("O título do lembrete não pode estar vazio.")

    rep = repeat_mode if repeat_mode in REPEAT_MODES else "none"
    now_iso = datetime.now().isoformat()
    target_iso = target_time.isoformat()

    path = init_reminders_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders (title, message, target_time, repeat_mode, is_active, triggered, created_at)
            VALUES (?, ?, ?, ?, 1, 0, ?)
        """, (t, message.strip(), target_iso, rep, now_iso))
        conn.commit()
        return cursor.lastrowid


def delete_reminder(reminder_id: int, db_path: Optional[Path] = None) -> bool:
    """Exclui um lembrete pelo ID."""
    path = init_reminders_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_reminder_active(reminder_id: int, db_path: Optional[Path] = None) -> bool:
    """Ativa ou desativa um lembrete agendado."""
    path = init_reminders_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM reminders WHERE id = ?", (reminder_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_state = 0 if row[0] else 1
        cursor.execute("UPDATE reminders SET is_active = ? WHERE id = ?", (new_state, reminder_id))
        conn.commit()
        return bool(new_state)


def list_reminders(include_inactive: bool = True, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Lista todos os lembretes cadastrados."""
    path = init_reminders_db(db_path)
    results: List[Dict[str, Any]] = []

    sql = "SELECT id, title, message, target_time, repeat_mode, is_active, triggered, created_at FROM reminders"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY is_active DESC, target_time ASC"

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        for r in cursor.fetchall():
            results.append({
                "id": r["id"],
                "title": r["title"],
                "message": r["message"],
                "target_time": r["target_time"],
                "repeat_mode": r["repeat_mode"],
                "is_active": bool(r["is_active"]),
                "triggered": bool(r["triggered"]),
                "created_at": r["created_at"]
            })

    return results


def check_due_reminders(
    current_time: Optional[datetime] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Verifica e retorna todos os lembretes ativos que atingiram o horário programado.
    Calcula a próxima ocorrência para itens com repetição ou desativa lembretes pontuais.
    """
    now = current_time or datetime.now()
    now_iso = now.isoformat()

    path = init_reminders_db(db_path)
    due_items: List[Dict[str, Any]] = []

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, message, target_time, repeat_mode, is_active 
            FROM reminders 
            WHERE is_active = 1 AND target_time <= ?
        """, (now_iso,))
        rows = cursor.fetchall()

        for r in rows:
            due_items.append({
                "id": r["id"],
                "title": r["title"],
                "message": r["message"],
                "target_time": r["target_time"],
                "repeat_mode": r["repeat_mode"]
            })

            rem_id = r["id"]
            rep = r["repeat_mode"]

            if rep == "daily":
                # Avança 1 dia
                target_dt = datetime.fromisoformat(r["target_time"]) + timedelta(days=1)
                cursor.execute("UPDATE reminders SET target_time = ? WHERE id = ?", (target_dt.isoformat(), rem_id))
            elif rep == "weekdays":
                # Avança para próximo dia útil
                target_dt = datetime.fromisoformat(r["target_time"]) + timedelta(days=1)
                while target_dt.weekday() >= 5:  # Sábado=5, Domingo=6
                    target_dt += timedelta(days=1)
                cursor.execute("UPDATE reminders SET target_time = ? WHERE id = ?", (target_dt.isoformat(), rem_id))
            elif rep == "weekly":
                # Avança 7 dias
                target_dt = datetime.fromisoformat(r["target_time"]) + timedelta(days=7)
                cursor.execute("UPDATE reminders SET target_time = ? WHERE id = ?", (target_dt.isoformat(), rem_id))
            else:
                # Disparo único: marca como disparado e desativa
                cursor.execute("UPDATE reminders SET is_active = 0, triggered = 1 WHERE id = ?", (rem_id,))

        conn.commit()

    return due_items
