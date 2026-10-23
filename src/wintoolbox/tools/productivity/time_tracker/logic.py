"""
Lógica pura de persistência e gerenciamento do rastreador de tempo (Time Tracker).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import csv
from datetime import datetime
import io
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("productivity.time_tracker")


def get_tracker_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados do rastreador de tempo."""
    app_dir = get_app_dir()
    db_dir = app_dir / "productivity"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "time_tracker.db"


def init_tracker_db(db_path: Optional[Path] = None) -> Path:
    """Inicializa as tabelas do Time Tracker no SQLite."""
    path = db_path or get_tracker_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity TEXT NOT NULL,
                project TEXT DEFAULT 'Geral',
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                notes TEXT DEFAULT ''
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_active ON time_entries(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_proj ON time_entries(project)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_start ON time_entries(start_time DESC)")
        conn.commit()

    return path


def start_time_entry(
    activity: str,
    project: str = "Geral",
    notes: str = "",
    db_path: Optional[Path] = None
) -> int:
    """Inicia uma nova atividade no cronômetro, parando qualquer outra em andamento."""
    act = activity.strip() or "Atividade sem nome"
    proj = project.strip() or "Geral"
    now_iso = datetime.now().isoformat()

    path = init_tracker_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()

        # Para entradas ativas anteriores
        cursor.execute("SELECT id, start_time FROM time_entries WHERE is_active = 1")
        for row in cursor.fetchall():
            active_id = row[0]
            st = datetime.fromisoformat(row[1])
            dur = max(0, int((datetime.now() - st).total_seconds()))
            cursor.execute("""
                UPDATE time_entries 
                SET is_active = 0, end_time = ?, duration_seconds = ? 
                WHERE id = ?
            """, (now_iso, dur, active_id))

        # Cria a nova entrada
        cursor.execute("""
            INSERT INTO time_entries (activity, project, start_time, is_active, notes)
            VALUES (?, ?, ?, 1, ?)
        """, (act, proj, now_iso, notes.strip()))
        conn.commit()
        return cursor.lastrowid


def stop_time_entry(
    entry_id: Optional[int] = None,
    db_path: Optional[Path] = None
) -> Optional[int]:
    """Para o cronômetro ativo atual ou o especificado."""
    path = init_tracker_db(db_path)
    now = datetime.now()
    now_iso = now.isoformat()

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        if entry_id:
            cursor.execute("SELECT id, start_time FROM time_entries WHERE id = ? AND is_active = 1", (entry_id,))
        else:
            cursor.execute("SELECT id, start_time FROM time_entries WHERE is_active = 1 ORDER BY start_time DESC LIMIT 1")

        row = cursor.fetchone()
        if not row:
            return None

        act_id, start_str = row[0], row[1]
        st = datetime.fromisoformat(start_str)
        dur = max(0, int((now - st).total_seconds()))

        cursor.execute("""
            UPDATE time_entries 
            SET is_active = 0, end_time = ?, duration_seconds = ? 
            WHERE id = ?
        """, (now_iso, dur, act_id))
        conn.commit()
        return act_id


def get_active_time_entry(db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retorna a atividade atualmente em execução, se houver."""
    path = init_tracker_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM time_entries WHERE is_active = 1 ORDER BY start_time DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None

        st = datetime.fromisoformat(row["start_time"])
        current_dur = max(0, int((datetime.now() - st).total_seconds()))

        return {
            "id": row["id"],
            "activity": row["activity"],
            "project": row["project"],
            "start_time": row["start_time"],
            "duration_seconds": current_dur,
            "is_active": True,
            "notes": row["notes"]
        }


def add_manual_time_entry(
    activity: str,
    project: str,
    duration_minutes: int,
    date_str: Optional[str] = None,
    notes: str = "",
    db_path: Optional[Path] = None
) -> int:
    """Adiciona um registro manual de tempo em minutos."""
    act = activity.strip() or "Atividade manual"
    proj = project.strip() or "Geral"
    dur_sec = max(60, int(duration_minutes * 60))

    now = datetime.now()
    now_iso = now.isoformat()

    path = init_tracker_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO time_entries (activity, project, start_time, end_time, duration_seconds, is_active, notes)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (act, proj, now_iso, now_iso, dur_sec, notes.strip()))
        conn.commit()
        return cursor.lastrowid


def delete_time_entry(entry_id: int, db_path: Optional[Path] = None) -> bool:
    """Remove um registro pelo ID."""
    path = init_tracker_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_time_entries(
    project: str = "",
    limit: int = 150,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Lista as entradas registradas no histórico."""
    path = init_tracker_db(db_path)
    results: List[Dict[str, Any]] = []

    sql = "SELECT id, activity, project, start_time, end_time, duration_seconds, is_active, notes FROM time_entries WHERE is_active = 0"
    params: List[Any] = []

    if project.strip():
        sql += " AND project = ?"
        params.append(project.strip())

    sql += " ORDER BY start_time DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        for r in cursor.fetchall():
            results.append({
                "id": r["id"],
                "activity": r["activity"],
                "project": r["project"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "duration_seconds": r["duration_seconds"],
                "notes": r["notes"]
            })

    return results


def get_project_time_summary(db_path: Optional[Path] = None) -> Dict[str, int]:
    """Retorna o total de segundos acumulados por projeto."""
    path = init_tracker_db(db_path)
    summary: Dict[str, int] = {}

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project, SUM(duration_seconds) 
            FROM time_entries 
            WHERE is_active = 0 
            GROUP BY project 
            ORDER BY SUM(duration_seconds) DESC
        """)
        for proj, total in cursor.fetchall():
            summary[proj or "Geral"] = total or 0

    return summary


def format_duration(seconds: int) -> str:
    """Formata segundos em HH:MM:SS ou formato amigável."""
    s = max(0, int(seconds))
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs:02d}h {mins:02d}m {secs:02d}s"
    return f"{mins:02d}m {secs:02d}s"


def export_time_entries_csv(entries: List[Dict[str, Any]]) -> str:
    """Exporta lista de registros para formato CSV com delimitador ';'."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["ID", "Atividade", "Projeto", "Início", "Término", "Duração (Segundos)", "Duração Formatada", "Notas"])

    for e in entries:
        writer.writerow([
            e.get("id", ""),
            e.get("activity", ""),
            e.get("project", ""),
            e.get("start_time", ""),
            e.get("end_time", ""),
            e.get("duration_seconds", 0),
            format_duration(e.get("duration_seconds", 0)),
            e.get("notes", "")
        ])

    return out.getvalue()
