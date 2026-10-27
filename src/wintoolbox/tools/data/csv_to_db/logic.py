"""
Lógica pura para conversão e migração de dados tabulares (CSV, TSV, DSV) para SQLite e SQL Scripts.
Implementa detecção de dialeto/delimitador, inferência precisa de tipos de dados (INTEGER, REAL, DATE, TEXT),
sanitização de nomes de colunas e gravação atômica em SQLite.

Zero dependências de interface gráfica.
"""
import csv
from datetime import datetime
import io
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


def sanitize_identifier(name: str) -> str:
    """
    Sanitiza um nome de coluna ou tabela para um identificador SQL válido.
    """
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
    clean = clean.strip("_")
    if not clean:
        clean = "coluna"
    if clean[0].isdigit():
        clean = f"col_{clean}"
    # Evita palavras reservadas padrão
    reserved = {"select", "insert", "update", "delete", "table", "from", "where", "group", "order", "by", "index"}
    if clean.lower() in reserved:
        clean = f"{clean}_val"
    return clean.lower()


def detect_delimiter(sample_text: str) -> str:
    """
    Detecta o delimitador mais provável (vírgula, ponto e vírgula, tabulação ou pipe).
    """
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text[:4096], delimiters=",;\t|")
        return dialect.delimiter
    except Exception:
        # Fallback por contagem
        counts = {
            ",": sample_text.count(","),
            ";": sample_text.count(";"),
            "\t": sample_text.count("\t"),
            "|": sample_text.count("|"),
        }
        return max(counts, key=counts.get) or ","


def _infer_type_for_value(val: str) -> str:
    v = val.strip()
    if not v:
        return "NULL"

    # Boolean
    if v.lower() in ("true", "false"):
        return "INTEGER"

    # Integer
    if re.match(r"^-?\d+$", v):
        return "INTEGER"

    # Float / Real (suporta 123.45 ou 123,45 com vírgula decimal)
    if re.match(r"^-?\d+\.\d+$", v):
        return "REAL"

    # Date / Datetime
    for date_fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            datetime.strptime(v, date_fmt)
            return "DATETIME" if " " in v else "DATE"
        except ValueError:
            pass

    return "TEXT"


def infer_schema(headers: List[str], rows: List[List[str]]) -> List[Dict[str, str]]:
    """
    Infere os tipos das colunas baseado nas amostras de dados.
    Ordem de prioridade / generalização: NULL < INTEGER < REAL < DATE < TEXT.
    """
    schema = []
    num_cols = len(headers)

    for col_idx in range(num_cols):
        raw_header = headers[col_idx]
        sanitized_col = sanitize_identifier(raw_header)

        # Amostra valores da coluna
        types_seen = set()
        sample_values = []
        for row in rows[:500]:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val:
                    types_seen.add(_infer_type_for_value(val))
                    if len(sample_values) < 3:
                        sample_values.append(val)

        # Resolução de tipo
        if "TEXT" in types_seen:
            final_type = "TEXT"
        elif "REAL" in types_seen:
            final_type = "REAL"
        elif "DATE" in types_seen or "DATETIME" in types_seen:
            final_type = "DATE"
        elif "INTEGER" in types_seen:
            final_type = "INTEGER"
        else:
            final_type = "TEXT"

        schema.append({
            "original_name": raw_header,
            "column_name": sanitized_col,
            "type": final_type,
            "sample": ", ".join(sample_values),
        })

    return schema


def read_csv_data(
    file_path: Path,
    delimiter: Optional[str] = None,
    encoding: str = "utf-8",
) -> Tuple[List[str], List[List[str]], List[Dict[str, str]]]:
    """
    Lê o arquivo CSV/TSV e retorna (headers, rows, schema).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    # Leitura com fallback de encoding
    try:
        content = path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1", errors="replace")

    if not delimiter:
        delimiter = detect_delimiter(content)

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    all_rows = list(reader)

    if not all_rows:
        return [], [], []

    headers = [h.strip() for h in all_rows[0]]
    data_rows = all_rows[1:]
    schema = infer_schema(headers, data_rows)

    return headers, data_rows, schema


def csv_to_sqlite(
    csv_path: Path,
    db_path: Path,
    table_name: str = "tabela_importada",
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Converte diretamente um arquivo CSV/TSV para um banco de dados SQLite físico.
    """
    headers, rows, schema = read_csv_data(csv_path, delimiter=delimiter)
    if not schema:
        raise ValueError("O arquivo CSV está vazio ou não possui colunas válidas.")

    table = sanitize_identifier(table_name)
    out_db = Path(db_path)
    out_db.parent.mkdir(parents=True, exist_ok=True)

    col_defs = [f'"{col["column_name"]}" {col["type"]}' for col in schema]
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_defs)});'

    col_names = [f'"{col["column_name"]}"' for col in schema]
    placeholders = ", ".join(["?"] * len(schema))
    insert_sql = f'INSERT INTO "{table}" ({", ".join(col_names)}) VALUES ({placeholders});'

    conn = sqlite3.connect(out_db)
    try:
        cursor = conn.cursor()
        cursor.execute(create_sql)

        # Prepara registros convertidos para tipos corretos
        converted_rows = []
        for r in rows:
            record = []
            for col_idx, col_meta in enumerate(schema):
                val = r[col_idx].strip() if col_idx < len(r) else ""
                col_type = col_meta["type"]

                if not val:
                    record.append(None)
                elif col_type == "INTEGER":
                    try:
                        record.append(int(val))
                    except ValueError:
                        record.append(val)
                elif col_type == "REAL":
                    try:
                        record.append(float(val.replace(",", ".")))
                    except ValueError:
                        record.append(val)
                else:
                    record.append(val)
            converted_rows.append(record)

        cursor.executemany(insert_sql, converted_rows)
        conn.commit()
    finally:
        conn.close()

    return {
        "db_path": str(out_db.resolve()),
        "table_name": table,
        "total_rows": len(rows),
        "total_columns": len(schema),
    }


def csv_to_sql_script(
    csv_path: Path,
    table_name: str = "tabela_importada",
    delimiter: Optional[str] = None,
) -> str:
    """
    Gera um script SQL completo (CREATE TABLE + INSERT INTO em transação) a partir do CSV.
    """
    headers, rows, schema = read_csv_data(csv_path, delimiter=delimiter)
    if not schema:
        return "-- O arquivo CSV está vazio."

    table = sanitize_identifier(table_name)
    col_defs = [f'  "{col["column_name"]}" {col["type"]}' for col in schema]
    create_sql = f'CREATE TABLE "{table}" (\n' + ",\n".join(col_defs) + "\n);"

    statements = [
        f"-- Script gerado automaticamente pelo WinToolbox",
        f"-- Tabela: {table} | Total de registros: {len(rows)}",
        "BEGIN TRANSACTION;",
        create_sql,
    ]

    col_names = ", ".join([f'"{col["column_name"]}"' for col in schema])

    for r in rows:
        values_sql = []
        for col_idx, col_meta in enumerate(schema):
            val = r[col_idx].strip() if col_idx < len(r) else ""
            col_type = col_meta["type"]

            if not val:
                values_sql.append("NULL")
            elif col_type in ("INTEGER", "REAL"):
                clean_num = val.replace(",", ".")
                values_sql.append(clean_num if re.match(r"^-?\d+(\.\d+)?$", clean_num) else f"'{val}'")
            else:
                escaped = val.replace("'", "''")
                values_sql.append(f"'{escaped}'")

        statements.append(f'INSERT INTO "{table}" ({col_names}) VALUES ({", ".join(values_sql)});')

    statements.append("COMMIT;")
    return "\n".join(statements) + "\n"
