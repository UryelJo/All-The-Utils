"""
Lógica pura de persistência e gerenciamento de tarefas (To-Do List).
Utiliza SQLite local desacoplado de bibliotecas gráficas.
"""
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("productivity.todo")

PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]


def get_todo_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados de tarefas."""
    app_dir = get_app_dir()
    db_dir = app_dir / "productivity"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "todos.db"


def init_todo_db(db_path: Optional[Path] = None) -> Path:
    """Inicializa as tabelas do To-Do no SQLite."""
    path = db_path or get_todo_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'Geral',
                priority TEXT DEFAULT 'Média',
                due_date TEXT,
                completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_todo_comp ON todos(completed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_todo_cat ON todos(category)")
        conn.commit()

    return path


def add_todo(
    title: str,
    description: str = "",
    category: str = "Geral",
    priority: str = "Média",
    due_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> int:
    """Adiciona uma nova tarefa."""
    t = title.strip()
    if not t:
        raise ValueError("O título da tarefa não pode estar vazio.")

    prio = priority if priority in PRIORITIES else "Média"
    cat = category.strip() or "Geral"
    now_iso = datetime.now().isoformat()

    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO todos (title, description, category, priority, due_date, completed, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (t, description.strip(), cat, prio, due_date, now_iso))
        conn.commit()
        return cursor.lastrowid


def update_todo(
    todo_id: int,
    title: str,
    description: str = "",
    category: str = "Geral",
    priority: str = "Média",
    due_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """Atualiza dados de uma tarefa existente."""
    t = title.strip()
    if not t:
        raise ValueError("O título da tarefa não pode estar vazio.")

    prio = priority if priority in PRIORITIES else "Média"
    cat = category.strip() or "Geral"

    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE todos 
            SET title = ?, description = ?, category = ?, priority = ?, due_date = ?
            WHERE id = ?
        """, (t, description.strip(), cat, prio, due_date, todo_id))
        conn.commit()
        return cursor.rowcount > 0


def toggle_todo_completed(todo_id: int, db_path: Optional[Path] = None) -> bool:
    """Alterna o status de concluído de uma tarefa. Retorna o novo estado."""
    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT completed FROM todos WHERE id = ?", (todo_id,))
        row = cursor.fetchone()
        if not row:
            return False

        new_status = 0 if row[0] else 1
        comp_date = datetime.now().isoformat() if new_status else None

        cursor.execute("UPDATE todos SET completed = ?, completed_at = ? WHERE id = ?", (new_status, comp_date, todo_id))
        conn.commit()
        return bool(new_status)


def delete_todo(todo_id: int, db_path: Optional[Path] = None) -> bool:
    """Remove uma tarefa pelo ID."""
    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_todos(
    category: str = "",
    priority: str = "",
    filter_status: str = "all",  # "all", "pending", "completed"
    search: str = "",
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Consulta tarefas com base em filtros e termo de pesquisa."""
    path = init_todo_db(db_path)
    todos: List[Dict[str, Any]] = []

    sql = "SELECT id, title, description, category, priority, due_date, completed, created_at, completed_at FROM todos WHERE 1=1"
    params: List[Any] = []

    if filter_status == "pending":
        sql += " AND completed = 0"
    elif filter_status == "completed":
        sql += " AND completed = 1"

    if category.strip():
        sql += " AND category = ?"
        params.append(category.strip())

    if priority.strip() and priority in PRIORITIES:
        sql += " AND priority = ?"
        params.append(priority.strip())

    if search.strip():
        sql += " AND (title LIKE ? OR description LIKE ?)"
        s = f"%{search.strip()}%"
        params.extend([s, s])

    # Ordenação: Pendentes primeiro, depois por prioridade/data
    sql += """
        ORDER BY completed ASC, 
        CASE priority 
            WHEN 'Urgente' THEN 1 
            WHEN 'Alta' THEN 2 
            WHEN 'Média' THEN 3 
            WHEN 'Baixa' THEN 4 
            ELSE 5 
        END ASC, 
        due_date ASC, created_at DESC
    """

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        for r in cursor.fetchall():
            todos.append({
                "id": r["id"],
                "title": r["title"],
                "description": r["description"],
                "category": r["category"],
                "priority": r["priority"],
                "due_date": r["due_date"],
                "completed": bool(r["completed"]),
                "created_at": r["created_at"],
                "completed_at": r["completed_at"]
            })

    return todos


def get_todo_categories(db_path: Optional[Path] = None) -> List[str]:
    """Retorna lista de categorias distintas cadastradas."""
    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM todos WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
        return [r[0] for r in cursor.fetchall()]


def get_todo_stats(db_path: Optional[Path] = None) -> Dict[str, int]:
    """Retorna contadores estatísticos das tarefas."""
    path = init_todo_db(db_path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM todos")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM todos WHERE completed = 1")
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM todos WHERE completed = 0")
        pending = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM todos WHERE completed = 0 AND priority IN ('Alta', 'Urgente')")
        high_prio = cursor.fetchone()[0]

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "high_priority": high_prio
        }
