"""
Lógica pura para preenchimento de modelos de texto (Mala Direta / Template Filler)
a partir de registros tabulares ou planilhas CSV.

Suporta:
- Sintaxe de placeholders `{{campo}}` ou `{{ campo }}`
- Modificadores de texto integrados: `{{campo | upper}}`, `{{campo | lower}}`, `{{campo | capitalize}}`, `{{campo | title}}`
- Detecção automática de delimitadores CSV (vírgula, ponto-e-vírgula, tabulação)
- Geração consolidada ou em múltiplos arquivos nomeados dinamicamente

Isolado de qualquer biblioteca de interface gráfica.
"""
import csv
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_\.\-]+)(?:\s*\|\s*([a-zA-Z0-9_]+))?\s*\}\}")


def extract_placeholders(template: str) -> List[str]:
    """
    Extrai todos os nomes únicos de campos/placeholders presentes no template,
    preservando a ordem de primeira aparição.
    """
    seen = set()
    result = []
    for match in PLACEHOLDER_REGEX.finditer(template):
        field_name = match.group(1).strip()
        if field_name not in seen:
            seen.add(field_name)
            result.append(field_name)
    return result


def apply_modifier(value: str, modifier: Optional[str]) -> str:
    """Aplica transformações de texto suportadas aos valores."""
    if not modifier:
        return value
    mod = modifier.lower().strip()
    if mod == "upper":
        return value.upper()
    if mod == "lower":
        return value.lower()
    if mod == "capitalize":
        return value.capitalize()
    if mod == "title":
        return value.title()
    if mod == "strip":
        return value.strip()
    return value


def fill_template(template: str, data: Dict[str, Any], default_val: str = "") -> str:
    """
    Substitui todos os placeholders `{{campo}}` pelos respectivos valores do dicionário.
    """
    def _replacer(match: re.Match) -> str:
        field_name = match.group(1).strip()
        modifier = match.group(2)
        val = data.get(field_name)
        if val is None:
            raw_str = default_val
        else:
            raw_str = str(val)
        return apply_modifier(raw_str, modifier)

    return PLACEHOLDER_REGEX.sub(_replacer, template)


def parse_csv_data(csv_content: str, delimiter: Optional[str] = None) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Interpreta uma string de CSV detectando delimitadores comuns (vírgula, ponto-e-vírgula, tab).
    Retorna lista de cabeçalhos e lista de dicionários por linha.
    """
    if not csv_content.strip():
        return [], []

    first_line = csv_content.strip().splitlines()[0]
    if delimiter is None:
        if ";" in first_line:
            delimiter = ";"
        elif "\t" in first_line:
            delimiter = "\t"
        else:
            delimiter = ","

    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f, delimiter=delimiter)
    headers = [h.strip() for h in (reader.fieldnames or []) if h]
    
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned_row = {
            (k.strip() if k else ""): (v.strip() if v else "")
            for k, v in row.items() if k
        }
        rows.append(cleaned_row)

    return headers, rows


def generate_batch_files(
    template: str,
    records: List[Dict[str, str]],
    output_dir: Path,
    filename_template: str = "documento_{{index}}.txt",
    default_val: str = ""
) -> List[Path]:
    """
    Gera múltiplos arquivos de saída preenchidos na pasta destino.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: List[Path] = []

    for idx, row in enumerate(records, start=1):
        context = dict(row)
        context["index"] = str(idx)

        # Preenche conteúdo
        filled_text = fill_template(template, context, default_val=default_val)

        # Preenche nome do arquivo
        out_name = fill_template(filename_template, context, default_val=f"item_{idx}")
        # Higieniza caracteres ilegais no Windows
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", out_name).strip()
        if not safe_name.endswith((".txt", ".md", ".html", ".csv", ".json")):
            safe_name += ".txt"

        dest_file = output_dir / safe_name
        dest_file.write_text(filled_text, encoding="utf-8")
        generated_paths.append(dest_file)

    return generated_paths
