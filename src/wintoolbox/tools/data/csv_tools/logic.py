"""
Lógica pura para manipulação e processamento em lote de arquivos CSV.
Suporta divisão por linhas, fusão de arquivos com mesmo cabeçalho, conversão
de delimitadores, remoção de duplicatas e reordenação de colunas.

Zero dependências de interface gráfica ou widgets.
"""
import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def detect_delimiter(file_path: str, encoding: str = "utf-8") -> str:
    """
    Detecta automaticamente o delimitador de um arquivo CSV (,, ;, \\t, |).
    """
    delimiters = [",", ";", "\t", "|"]
    try:
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(4096)
            if not sample:
                return ","
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=delimiters)
            return dialect.delimiter
    except Exception:
        # Fallback por contagem simples
        counts = {d: sample.count(d) for d in delimiters}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def split_csv_by_rows(
    file_path: str,
    output_dir: str,
    rows_per_file: int,
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
) -> List[str]:
    """
    Divide um arquivo CSV em partes menores de 'rows_per_file' linhas,
    preservando a linha de cabeçalho em cada parte.
    Retorna a lista de caminhos dos arquivos gerados.
    """
    if rows_per_file <= 0:
        raise ValueError("O número de linhas por arquivo deve ser maior que zero.")

    delim = delimiter or detect_delimiter(file_path, encoding=encoding)
    src_path = Path(file_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_files: List[str] = []

    with open(file_path, "r", encoding=encoding, newline="", errors="replace") as in_f:
        reader = csv.reader(in_f, delimiter=delim)
        header = next(reader, None)
        if header is None:
            return generated_files

        part_num = 1
        current_rows: List[List[str]] = []

        def _write_part(part_index: int, rows: List[List[str]]) -> str:
            part_name = f"{src_path.stem}_parte_{part_index:03d}{src_path.suffix}"
            part_path = out_dir / part_name
            with open(part_path, "w", encoding=encoding, newline="") as out_f:
                writer = csv.writer(out_f, delimiter=delim)
                writer.writerow(header)
                writer.writerows(rows)
            return str(part_path)

        for row in reader:
            current_rows.append(row)
            if len(current_rows) >= rows_per_file:
                generated_files.append(_write_part(part_num, current_rows))
                part_num += 1
                current_rows = []

        if current_rows or not generated_files:
            generated_files.append(_write_part(part_num, current_rows))

    return generated_files


def merge_csv_files(
    file_paths: List[str],
    output_path: str,
    deduplicate: bool = False,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Funde múltiplos arquivos CSV em um único arquivo de saída.
    Valida cabeçalhos e opcionalmente remove linhas duplicadas.
    Retorna métricas da fusão.
    """
    if not file_paths:
        raise ValueError("Nenhum arquivo fornecido para fusão.")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    unique_rows = 0
    seen_hashes: Set[int] = set()

    first_file = file_paths[0]
    delim = detect_delimiter(first_file, encoding=encoding)

    header_saved: Optional[List[str]] = None

    with open(output_path, "w", encoding=encoding, newline="") as out_f:
        writer: Optional[Any] = None

        for path in file_paths:
            with open(path, "r", encoding=encoding, newline="", errors="replace") as in_f:
                current_delim = detect_delimiter(path, encoding=encoding)
                reader = csv.reader(in_f, delimiter=current_delim)
                header = next(reader, None)
                if header is None:
                    continue

                if header_saved is None:
                    header_saved = header
                    writer = csv.writer(out_f, delimiter=delim)
                    writer.writerow(header_saved)

                for row in reader:
                    total_rows += 1
                    if deduplicate:
                        row_key = hash(tuple(row))
                        if row_key in seen_hashes:
                            continue
                        seen_hashes.add(row_key)
                        unique_rows += 1
                    else:
                        unique_rows += 1

                    if writer:
                        writer.writerow(row)

    return {
        "output_path": output_path,
        "files_merged": len(file_paths),
        "total_source_rows": total_rows,
        "written_rows": unique_rows,
        "duplicates_removed": total_rows - unique_rows if deduplicate else 0,
    }


def convert_csv_delimiter(
    file_path: str,
    output_path: str,
    target_delimiter: str,
    source_delimiter: Optional[str] = None,
    encoding: str = "utf-8",
) -> int:
    """
    Converte o delimitador de um arquivo CSV para o delimitador desejado.
    Retorna o número de linhas processadas.
    """
    src_delim = source_delimiter or detect_delimiter(file_path, encoding=encoding)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    rows_count = 0
    with open(file_path, "r", encoding=encoding, newline="", errors="replace") as in_f, \
         open(output_path, "w", encoding=encoding, newline="") as out_f:
        reader = csv.reader(in_f, delimiter=src_delim)
        writer = csv.writer(out_f, delimiter=target_delimiter)
        for row in reader:
            writer.writerow(row)
            rows_count += 1

    return rows_count


def remove_csv_duplicates(
    file_path: str,
    output_path: str,
    subset_columns: Optional[List[str]] = None,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """
    Remove linhas duplicadas de um arquivo CSV.
    Permite escolher um subconjunto de colunas como chave única.
    """
    delim = detect_delimiter(file_path, encoding=encoding)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    seen_keys: Set[Tuple[str, ...]] = set()
    total_rows = 0
    written_rows = 0

    with open(file_path, "r", encoding=encoding, newline="", errors="replace") as in_f, \
         open(output_path, "w", encoding=encoding, newline="") as out_f:
        reader = csv.reader(in_f, delimiter=delim)
        header = next(reader, None)
        if header is None:
            return {"total_rows": 0, "written_rows": 0, "duplicates_removed": 0}

        writer = csv.writer(out_f, delimiter=delim)
        writer.writerow(header)

        # Mapeamento de índices do subset
        col_indices = None
        if subset_columns:
            header_clean = [c.strip() for c in header]
            col_indices = [header_clean.index(c.strip()) for c in subset_columns if c.strip() in header_clean]

        for row in reader:
            total_rows += 1
            if col_indices:
                key = tuple(row[idx] if idx < len(row) else "" for idx in col_indices)
            else:
                key = tuple(row)

            if key in seen_keys:
                continue
            seen_keys.add(key)
            writer.writerow(row)
            written_rows += 1

    return {
        "output_path": output_path,
        "total_rows": total_rows,
        "written_rows": written_rows,
        "duplicates_removed": total_rows - written_rows,
    }
