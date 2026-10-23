"""
Lógica pura de persistência e gerenciamento do histórico da área de transferência.
Utiliza banco SQLite local desacoplado de bibliotecas de interface de usuário.
"""
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("productivity.clipboard_history")


def get_clipboard_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados do histórico da área de transferência."""
    app_dir = get_app_dir()
    db_dir = app_dir / "productivity"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "clipboard_history.db"


def init_clipboard_db(db_path: Optional[Path] = None) -> Path:
    """Inicializa as tabelas do histórico no banco SQLite."""
    path = db_path or get_clipboard_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                is_favorite INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_fav ON clipboard_items(is_favorite)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clip_updated ON clipboard_items(updated_at DESC)")
        conn.commit()

    return path


def add_clipboard_item(
    content: str,
    db_path: Optional[Path] = None,
    max_history: int = 500
) -> Optional[int]:
    """
    Adiciona ou atualiza um item na área de transferência.
    Se o item mais recente for idêntico, apenas atualiza updated_at.
    """
    text = content.strip()
    if not text:
        return None

    path = init_clipboard_db(db_path)
    now_iso = datetime.now().isoformat()
    char_len = len(text)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()

        # Verifica o item mais recente
        cursor.execute("SELECT id, content FROM clipboard_items ORDER BY updated_at DESC LIMIT 1")
        last_row = cursor.fetchone()

        if last_row and last_row[1] == text:
            # Já é o item mais recente, atualiza data
            cursor.execute("UPDATE clipboard_items SET updated_at = ? WHERE id = ?", (now_iso, last_row[0]))
            conn.commit()
            return last_row[0]

        # Verifica se já existe em outro lugar do histórico para evitar duplicação em excesso
        cursor.execute("SELECT id, is_favorite FROM clipboard_items WHERE content = ? LIMIT 1", (text,))
        existing = cursor.fetchone()

        if existing:
            item_id = existing[0]
            cursor.execute("UPDATE clipboard_items SET updated_at = ? WHERE id = ?", (now_iso, item_id))
            conn.commit()
            return item_id

        # Novo item
        cursor.execute("""
            INSERT INTO clipboard_items (content, char_count, is_favorite, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?)
        """, (text, char_len, now_iso, now_iso))
        new_id = cursor.lastrowid

        # Limpeza para respeitar max_history (sem deletar favoritos)
        cursor.execute("""
            DELETE FROM clipboard_items 
            WHERE is_favorite = 0 AND id NOT IN (
                SELECT id FROM clipboard_items 
                WHERE is_favorite = 0 
                ORDER BY updated_at DESC LIMIT ?
            )
        """, (max_history,))

        conn.commit()
        return new_id


def list_clipboard_items(
    db_path: Optional[Path] = None,
    query: str = "",
    favorites_only: bool = False,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Consulta itens do histórico com filtros e busca."""
    path = init_clipboard_db(db_path)
    items: List[Dict[str, Any]] = []

    sql = "SELECT id, content, char_count, is_favorite, created_at, updated_at FROM clipboard_items WHERE 1=1"
    params: List[Any] = []

    if favorites_only:
        sql += " AND is_favorite = 1"

    if query.strip():
        sql += " AND content LIKE ?"
        params.append(f"%{query.strip()}%")

    sql += " ORDER BY is_favorite DESC, updated_at DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        for row in cursor.fetchall():
            items.append({
                "id": row["id"],
                "content": row["content"],
                "char_count": row["char_count"],
                "is_favorite": bool(row["is_favorite"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })

    return items


def toggle_clipboard_favorite(item_id: int, db_path: Optional[Path] = None) -> bool:
    """Alterna o status de favorito de um item. Retorna o novo estado."""
    path = init_clipboard_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_favorite FROM clipboard_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return False
        new_state = 0 if row[0] else 1
        cursor.execute("UPDATE clipboard_items SET is_favorite = ? WHERE id = ?", (new_state, item_id))
        conn.commit()
        return bool(new_state)


def delete_clipboard_item(item_id: int, db_path: Optional[Path] = None) -> bool:
    """Remove um item do histórico pelo ID."""
    path = init_clipboard_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_clipboard_history(keep_favorites: bool = True, db_path: Optional[Path] = None) -> int:
    """Limpa o histórico da área de transferência."""
    path = init_clipboard_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        if keep_favorites:
            cursor.execute("DELETE FROM clipboard_items WHERE is_favorite = 0")
        else:
            cursor.execute("DELETE FROM clipboard_items")
        conn.commit()
        return cursor.rowcount
