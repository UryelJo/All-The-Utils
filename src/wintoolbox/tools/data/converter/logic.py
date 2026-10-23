"""
Lógica pura de conversão estruturada de dados: JSON ↔ YAML ↔ CSV ↔ XML.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

import yaml
# defusedxml: o parser padrão aceita "billion laughs" e entidades externas em XML recebido
try:
    from defusedxml.ElementTree import fromstring as safe_xml_fromstring
except ImportError:
    from xml.etree.ElementTree import fromstring as safe_xml_fromstring


# Carregadores em C (libyaml) quando disponíveis: várias vezes mais rápidos, mesma segurança
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_YAML_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def read_text_auto(file_path: Path) -> str:
    """UTF-8 (com ou sem BOM) e, em seguida, cp1252: CSVs do Excel em pt-BR vêm em ANSI."""
    raw = file_path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")

def load_data(file_path: Path) -> Any:
    """Lê um arquivo de dados estruturado e converte em estruturas nativas Python (dict/list)."""
    ext = file_path.suffix.lower()
    content = read_text_auto(file_path)

    if ext in (".json",):
        return json.loads(content)
    elif ext in (".yaml", ".yml"):
        return yaml.load(content, Loader=_YAML_LOADER)
    elif ext in (".csv",):
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)
    elif ext in (".xml",):
        root = safe_xml_fromstring(content)
        return _xml_to_dict(root)
    else:
        raise ValueError(f"Extensão {ext} não suportada para leitura de dados.")

def save_data(data: Any, out_path: Path, target_format: str) -> None:
    """Exporta estruturas de dados Python no formato de destino desejado."""
    fmt = target_format.upper()

    if fmt == "JSON":
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt == "YAML":
        out_path.write_text(yaml.dump(data, Dumper=_YAML_DUMPER, allow_unicode=True, sort_keys=False), encoding="utf-8")
    elif fmt == "CSV":
        # Converte lista de dicionários para CSV
        if isinstance(data, dict):
            # Se for um dict único, transforma em lista de 1 linha ou de chave/valor
            data = [data]
        elif not isinstance(data, list):
            data = [{"valor": str(data)}]

        if not data or not isinstance(data[0], dict):
            # Formato simples
            data = [{"item": str(x)} for x in data]

        headers = list(data[0].keys())
        out_s = io.StringIO()
        writer = csv.DictWriter(out_s, fieldnames=headers)
        writer.writeheader()
        for row in data:
            if isinstance(row, dict):
                writer.writerow(row)
        out_path.write_text(out_s.getvalue(), encoding="utf-8")
    elif fmt == "XML":
        root = _dict_to_xml("dados", data)
        xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        out_path.write_text(xml_str, encoding="utf-8")
    else:
        raise ValueError(f"Formato de saída {target_format} não suportado.")

def _xml_to_dict(element: ET.Element) -> Any:
    """Converte um ElementTree XML em dict ou lista."""
    children = list(element)
    if not children:
        return element.text

    d = {}
    for child in children:
        child_data = _xml_to_dict(child)
        if child.tag in d:
            if not isinstance(d[child.tag], list):
                d[child.tag] = [d[child.tag]]
            d[child.tag].append(child_data)
        else:
            d[child.tag] = child_data
    return d

def _dict_to_xml(tag: str, d: Any) -> ET.Element:
    """Converte dict ou list em ElementTree XML."""
    elem = ET.Element(tag)
    if isinstance(d, dict):
        for key, val in d.items():
            child = _dict_to_xml(key, val)
            elem.append(child)
    elif isinstance(d, list):
        for item in d:
            child = _dict_to_xml("item", item)
            elem.append(child)
    else:
        elem.text = str(d) if d is not None else ""
    return elem
