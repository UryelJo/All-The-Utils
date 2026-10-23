"""
Lógica pura de persistência e gerenciamento do bloco de notas rápidas.
Isolada de bibliotecas de interface visual.
"""
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("productivity.quick_notes")


def get_notes_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados de anotações rápidas."""
    app_dir = get_app_dir()
    db_dir = app_dir / "productivity"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "quick_notes.db"


def init_notes_db(db_path: Optional[Path] = None) -> Path:
    """Inicializa as tabelas de notas no SQLite."""
    path = db_path or get_notes_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                category TEXT DEFAULT 'Geral',
                is_pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_pin ON notes(is_pinned DESC, updated_at DESC)")
        conn.commit()

    return path


def create_note(
    title: str = "Nova Nota",
    content: str = "",
    category: str = "Geral",
    db_path: Optional[Path] = None
) -> int:
    """Cria uma nova anotação e retorna o ID."""
    t = title.strip() or "Nova Nota"
    cat = category.strip() or "Geral"
    now_iso = datetime.now().isoformat()

    path = init_notes_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes (title, content, category, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?)
        """, (t, content, cat, now_iso, now_iso))
        conn.commit()
        return cursor.lastrowid


def update_note(
    note_id: int,
    title: str,
    content: str,
    category: str = "Geral",
    db_path: Optional[Path] = None
) -> bool:
    """Atualiza o conteúdo de uma anotação."""
    t = title.strip() or "Sem título"
    cat = category.strip() or "Geral"
    now_iso = datetime.now().isoformat()

    path = init_notes_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notes 
            SET title = ?, content = ?, category = ?, updated_at = ?
            WHERE id = ?
        """, (t, content, cat, now_iso, note_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_note(note_id: int, db_path: Optional[Path] = None) -> bool:
    """Exclui uma anotação pelo ID."""
    path = init_notes_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_note_pin(note_id: int, db_path: Optional[Path] = None) -> bool:
    """Alterna o status de fixação (pinned) de uma nota."""
    path = init_notes_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_state = 0 if row[0] else 1
        cursor.execute("UPDATE notes SET is_pinned = ? WHERE id = ?", (new_state, note_id))
        conn.commit()
        return bool(new_state)


def list_notes(
    query: str = "",
    category: str = "",
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Consulta todas as notas ordenando as fixadas primeiro."""
    path = init_notes_db(db_path)
    results: List[Dict[str, Any]] = []

    sql = "SELECT id, title, content, category, is_pinned, created_at, updated_at FROM notes WHERE 1=1"
    params: List[Any] = []

    if category.strip():
        sql += " AND category = ?"
        params.append(category.strip())

    if query.strip():
        sql += " AND (title LIKE ? OR content LIKE ?)"
        s = f"%{query.strip()}%"
        params.extend([s, s])

    sql += " ORDER BY is_pinned DESC, updated_at DESC"

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        for r in cursor.fetchall():
            results.append({
                "id": r["id"],
                "title": r["title"],
                "content": r["content"],
                "category": r["category"],
                "is_pinned": bool(r["is_pinned"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })

    return results


def get_note_by_id(note_id: int, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retorna uma nota específica pelo ID."""
    path = init_notes_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, content, category, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (note_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "category": r["category"],
            "is_pinned": bool(r["is_pinned"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }


def count_words_and_chars(text: str) -> Tuple[int, int]:
    """Calcula quantidade de palavras e caracteres de um texto."""
    if not text:
        return 0, 0
    words = len(text.split())
    chars = len(text)
    return words, chars


def export_note_text(note: Dict[str, Any], format_type: str = "md") -> str:
    """Exporta a nota formatada em Markdown ou Texto simples."""
    title = note.get("title", "Anotação")
    content = note.get("content", "")
    updated = note.get("updated_at", "")

    if format_type.lower() == "md":
        return f"# {title}\n\n*Última modificação: {updated}*\n\n---\n\n{content}\n"
    return f"{title}\n{'=' * len(title)}\n\n{content}\n"
