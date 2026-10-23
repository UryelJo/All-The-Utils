"""
Lógica pura do Visualizador de Bancos de Dados SQLite.
Abertura somente-leitura segura, introspecção de esquema e execução de consultas SQL.
Zero acoplamento com interface gráfica.
"""
import csv
import io
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.sqlite_viewer")


def get_sqlite_readonly_uri(db_path: Path) -> str:
    """Retorna uma URI SQLite em modo somente leitura (mode=ro)."""
    # Converte caminhos do Windows para formato de URI URI compatível
    resolved = db_path.resolve().as_posix()
    return f"file:{resolved}?mode=ro"


def list_tables_and_views(db_path: Path) -> List[Dict[str, Any]]:
    """Lista todas as tabelas e views do banco SQLite com contagem de registros e DDL."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Arquivo de banco de dados não encontrado: {db_path}")

    uri = get_sqlite_readonly_uri(db_path)
    results: List[Dict[str, Any]] = []

    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        cursor = conn.cursor()

        # Busca tabelas e views excluindo as tabelas internas do sistema SQLite
        cursor.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type ASC, name ASC
            """
        )
        rows = cursor.fetchall()

        for obj_type, name, ddl in rows:
            count = 0
            try:
                # Contagem rápida se for tabela comum
                c_cur = conn.cursor()
                # Escapa nomes de tabelas com colchetes
                c_cur.execute(f"SELECT COUNT(*) FROM [{name}]")
                count_res = c_cur.fetchone()
                if count_res:
                    count = count_res[0]
            except Exception:
                count = -1

            results.append({
                "name": name,
                "type": "Tabela" if obj_type == "table" else "Visualização (View)",
                "count": count,
                "ddl": ddl or ""
            })

        conn.close()
    except Exception as e:
        _log.exception("Erro ao inspecionar tabelas do banco %s", db_path)
        raise RuntimeError(f"Falha ao ler banco SQLite: {e}") from e

    return results


def get_table_schema(db_path: Path, table_name: str) -> List[Dict[str, Any]]:
    """Retorna o esquema de colunas de uma tabela via PRAGMA table_info."""
    uri = get_sqlite_readonly_uri(db_path)
    columns: List[Dict[str, Any]] = []

    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        rows = cursor.fetchall()
        for r in rows:
            # cid, name, type, notnull, dflt_value, pk
            columns.append({
                "cid": r[0],
                "name": r[1],
                "type": r[2] or "ANY",
                "notnull": bool(r[3]),
                "default": str(r[4]) if r[4] is not None else "",
                "pk": bool(r[5])
            })
        conn.close()
    except Exception as e:
        _log.warning("Falha ao obter esquema da tabela %s: %s", table_name, e)
        raise

    return columns


def execute_query(
    db_path: Path,
    sql: str,
    max_rows: int = 1000
) -> Tuple[List[str], List[Dict[str, Any]], float]:
    """
    Executa uma consulta SQL em modo somente-leitura.
    Retorna (colunas, lista_de_registros, tempo_execucao_segundos).
    """
    sql_clean = sql.strip()
    if not sql_clean:
        return [], [], 0.0

    uri = get_sqlite_readonly_uri(db_path)
    t0 = time.perf_counter()

    conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(sql_clean)
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(max_rows)
        data = [dict(row) for row in rows]
    finally:
        conn.close()

    elapsed = time.perf_counter() - t0
    return col_names, data, elapsed


def export_query_results(data: List[Dict[str, Any]], format_type: str = "csv") -> str:
    """Exporta os resultados de uma consulta para CSV ou JSON."""
    if not data:
        return ""

    fmt = format_type.lower().strip()
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    # CSV padrão
    out = io.StringIO()
    cols = list(data[0].keys())
    writer = csv.DictWriter(out, fieldnames=cols, delimiter=";")
    writer.writeheader()
    writer.writerows(data)
    return out.getvalue()
