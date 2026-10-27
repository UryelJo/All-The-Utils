"""
Lógica pura para carregamento de arquivos tabulares (CSV, JSON) em banco SQLite
em memória e execução de consultas SQL analíticas.

Zero dependências de interface gráfica ou widgets.
"""
import csv
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def sanitize_table_name(raw_name: str) -> str:
    """Sanitiza o nome de uma tabela para evitar SQL Injection em DDL."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name.strip())
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned.lower()


def infer_column_type(values: List[str]) -> str:
    """Inferência de tipo SQLite simples para uma coluna com base em amostras."""
    has_real = False
    has_text = False
    has_values = False

    for v in values:
        s = v.strip()
        if not s:
            continue
        has_values = True
        # Tenta int
        try:
            int(s)
            continue
        except ValueError:
            pass

        # Tenta float
        try:
            float(s.replace(",", "."))
            has_real = True
            continue
        except ValueError:
            has_text = True
            break

    if not has_values or has_text:
        return "TEXT"
    if has_real:
        return "REAL"
    return "INTEGER"


def import_csv_to_sqlite(
    conn: sqlite3.Connection,
    file_path: str,
    table_name: Optional[str] = None,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Importa um arquivo CSV para uma tabela no banco SQLite.
    Infere tipos automaticamente e sanitiza nomes de colunas.
    """
    p = Path(file_path)
    tbl_name = sanitize_table_name(table_name or p.stem)

    with open(file_path, "r", encoding=encoding, newline="", errors="replace") as f:
        # Detecta delimitador
        sample = f.read(4096)
        f.seek(0)
        delim = ","
        if sample:
            for d in [";", "\t", "|", ","]:
                if d in sample and sample.count(d) > sample.count(delim):
                    delim = d

        reader = csv.reader(f, delimiter=delim)
        header = next(reader, None)
        if not header:
            raise ValueError("Arquivo CSV vazio ou sem cabeçalho.")

        # Amostra de linhas para inferência de tipos
        sample_rows = []
        all_rows = []
        for idx, row in enumerate(reader):
            all_rows.append(row)
            if idx < 100:
                sample_rows.append(row)

        col_defs = []
        sanitized_col_names = []
        for col_idx, col_name in enumerate(header):
            s_name = sanitize_table_name(col_name) or f"col_{col_idx}"
            sanitized_col_names.append(s_name)
            col_samples = [r[col_idx] for r in sample_rows if col_idx < len(r)]
            col_type = infer_column_type(col_samples)
            col_defs.append(f'"{s_name}" {col_type}')

        # Cria tabela
        drop_sql = f'DROP TABLE IF EXISTS "{tbl_name}"'
        create_sql = f'CREATE TABLE "{tbl_name}" ({", ".join(col_defs)})'
        conn.execute(drop_sql)
        conn.execute(create_sql)

        # Insere dados
        placeholders = ", ".join(["?"] * len(sanitized_col_names))
        insert_sql = f'INSERT INTO "{tbl_name}" VALUES ({placeholders})'

        # Normaliza número de colunas das linhas
        padded_rows = []
        for r in all_rows:
            if len(r) < len(sanitized_col_names):
                padded_rows.append(r + [""] * (len(sanitized_col_names) - len(r)))
            else:
                padded_rows.append(r[:len(sanitized_col_names)])

        conn.executemany(insert_sql, padded_rows)
        conn.commit()

    return {
        "table_name": tbl_name,
        "columns": sanitized_col_names,
        "row_count": len(all_rows),
    }


def import_json_to_sqlite(
    conn: sqlite3.Connection,
    file_path: str,
    table_name: Optional[str] = None,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Importa um arquivo JSON (lista de objetos ou dicionário com chave de dados) para o SQLite.
    """
    p = Path(file_path)
    tbl_name = sanitize_table_name(table_name or p.stem)

    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        data = json.load(f)

    items: List[Dict[str, Any]] = []
    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        # Procura primeira chave cujo valor seja uma lista de dicts
        for val in data.values():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                items = val
                break
        if not items:
            items = [data]

    if not items:
        raise ValueError("Estrutura JSON não contém lista de objetos tabulares.")

    # Descobre todas as chaves únicas
    all_keys: List[str] = []
    seen = set()
    for item in items:
        for k in item.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    sanitized_cols = [sanitize_table_name(k) for k in all_keys]
    col_defs = [f'"{c}" TEXT' for c in sanitized_cols]

    drop_sql = f'DROP TABLE IF EXISTS "{tbl_name}"'
    create_sql = f'CREATE TABLE "{tbl_name}" ({", ".join(col_defs)})'
    conn.execute(drop_sql)
    conn.execute(create_sql)

    placeholders = ", ".join(["?"] * len(all_keys))
    insert_sql = f'INSERT INTO "{tbl_name}" VALUES ({placeholders})'

    rows_to_insert = []
    for item in items:
        row = []
        for k in all_keys:
            v = item.get(k)
            if v is None:
                row.append(None)
            elif isinstance(v, (dict, list)):
                row.append(json.dumps(v, ensure_ascii=False))
            else:
                row.append(str(v))
        rows_to_insert.append(row)

    conn.executemany(insert_sql, rows_to_insert)
    conn.commit()

    return {
        "table_name": tbl_name,
        "columns": sanitized_cols,
        "row_count": len(rows_to_insert),
    }


def execute_sql_query(
    conn: sqlite3.Connection,
    query: str,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """
    Executa uma consulta SQL no banco de dados e retorna resultados paginados.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "elapsed_ms": 0.0,
            "error": "Consulta SQL vazia.",
        }

    start_time = time.perf_counter()
    try:
        cursor = conn.cursor()
        cursor.execute(clean_query)

        if cursor.description is None:
            # Query sem retorno (UPDATE, INSERT, DROP, etc)
            conn.commit()
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "columns": ["Mensagem"],
                "rows": [[f"Comando executado com sucesso. Linhas afetadas: {cursor.rowcount}"]],
                "row_count": cursor.rowcount,
                "elapsed_ms": round(elapsed_ms, 2),
                "error": "",
            }

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchmany(max_rows)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Converte valores para strings / formatos serializáveis
        processed_rows = []
        for r in rows:
            processed_rows.append([str(v) if v is not None else "" for v in r])

        return {
            "columns": columns,
            "rows": processed_rows,
            "row_count": len(processed_rows),
            "elapsed_ms": round(elapsed_ms, 2),
            "error": "",
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "elapsed_ms": round(elapsed_ms, 2),
            "error": str(exc),
        }


def export_query_results(
    columns: List[str],
    rows: List[List[Any]],
    format_type: str = "csv",
) -> str:
    """
    Exporta resultados tabulares para strings nos formatos CSV, JSON, Markdown ou HTML.
    """
    fmt = format_type.lower()

    if fmt == "csv":
        import io
        out = io.StringIO()
        writer = csv.writer(out, delimiter=";")
        writer.writerow(columns)
        writer.writerows(rows)
        return out.getvalue()

    elif fmt == "json":
        data = []
        for r in rows:
            obj = {col: (r[i] if i < len(r) else None) for i, col in enumerate(columns)}
            data.append(obj)
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif fmt == "markdown":
        if not columns:
            return ""
        header_line = "| " + " | ".join(columns) + " |"
        sep_line = "| " + " | ".join(["---"] * len(columns)) + " |"
        lines = [header_line, sep_line]
        for r in rows:
            escaped = [str(cell).replace("|", "\\|") for cell in r]
            lines.append("| " + " | ".join(escaped) + " |")
        return "\n".join(lines)

    elif fmt == "html":
        lines = ["<table border='1'>", "  <thead><tr>"]
        for c in columns:
            lines.append(f"    <th>{c}</th>")
        lines.extend(["  </tr></thead>", "  <tbody>"])
        for r in rows:
            lines.append("    <tr>")
            for cell in r:
                lines.append(f"      <td>{cell}</td>")
            lines.append("    </tr>")
        lines.extend(["  </tbody>", "</table>"])
        return "\n".join(lines)

    return ""
