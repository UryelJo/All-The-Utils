"""
Lógica pura para extração em lote de dados estruturados via Expressões Regulares (Regex).
Suporta padrões embutidos (e-mails, URLs, IPv4, CPFs, CNPJs, UUIDs, datas, telefones)
e padrões customizados com desduplicação e exportação para CSV, TSV e JSON.

Zero dependências de interface gráfica.
"""
import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple

BUILTIN_PATTERNS: Dict[str, Dict[str, str]] = {
    "emails": {
        "name": "E-mails",
        "pattern": r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]*[a-zA-Z0-9]\b",
        "desc": "Endereços de correio eletrônico padrão",
    },
    "urls": {
        "name": "URLs / Links Web",
        "pattern": r"https?://[^\s\"'<>]+",
        "desc": "Links HTTP e HTTPS",
    },
    "ipv4": {
        "name": "Endereços IPv4",
        "pattern": r"\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "desc": "Endereços IP versão 4 válidos",
    },
    "cpf": {
        "name": "CPF (Brasil)",
        "pattern": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b",
        "desc": "Cadastro de Pessoas Físicas formatado ou dígitos",
    },
    "cnpj": {
        "name": "CNPJ (Brasil)",
        "pattern": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
        "desc": "Cadastro Nacional da Pessoa Jurídica formatado",
    },
    "uuid": {
        "name": "UUIDs / GUIDs",
        "pattern": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "desc": "Identificadores únicos universais padrão",
    },
    "datas": {
        "name": "Datas (ISO e BR)",
        "pattern": r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b",
        "desc": "Formatos YYYY-MM-DD ou DD/MM/YYYY",
    },
    "telefones_br": {
        "name": "Telefones e Celulares BR",
        "pattern": r"(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-.\s]?\d{4}",
        "desc": "Telefones fixos e celulares brasileiros",
    },
}


def extract_structured_data(
    text: str,
    pattern: str,
    pattern_label: str = "Personalizado",
    deduplicate: bool = True,
    ignore_case: bool = True,
) -> List[Dict[str, Any]]:
    """
    Executa a extração por regex no texto e retorna a lista de registros estruturados.
    """
    if not text or not pattern:
        return []

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        raise ValueError(f"Expressão regular inválida: {exc}") from exc

    results: List[Dict[str, Any]] = []
    seen_values = set()
    idx = 1

    for match in regex.finditer(text):
        val = match.group(0).strip().rstrip(".,;:!?)]")
        if not val:
            continue

        normalized_key = val.lower() if ignore_case else val
        if deduplicate and normalized_key in seen_values:
            continue

        seen_values.add(normalized_key)

        start_pos, end_pos = match.span()
        results.append({
            "index": idx,
            "value": val,
            "type": pattern_label,
            "position": f"{start_pos}:{end_pos}",
            "length": len(val),
        })
        idx += 1

    return results


def export_records_to_text(records: List[Dict[str, Any]], format_type: str = "list") -> str:
    """
    Exporta a lista de registros para o formato solicitado:
    - 'list': apenas os valores, um por linha.
    - 'csv': formato CSV com cabeçalho.
    - 'tsv': formato TSV com tabulações.
    - 'json': array de objetos JSON formatado.
    """
    if not records:
        return ""

    fmt = format_type.lower().strip()

    if fmt == "list":
        return "\n".join(r["value"] for r in records) + "\n"

    elif fmt in ("csv", "tsv"):
        sep = "\t" if fmt == "tsv" else ","
        output = io.StringIO()
        writer = csv.writer(output, delimiter=sep)
        writer.writerow(["#", "Valor", "Tipo", "Posição", "Comprimento"])
        for r in records:
            writer.writerow([r["index"], r["value"], r["type"], r["position"], r["length"]])
        return output.getvalue()

    elif fmt == "json":
        return json.dumps(records, indent=2, ensure_ascii=False)

    return ""
