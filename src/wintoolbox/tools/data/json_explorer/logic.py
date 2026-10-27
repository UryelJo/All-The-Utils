"""
Lógica pura para o Explorador e Visualizador em Árvore de JSON.
Fornece parsing seguro, busca estruturada de chaves e valores, geração de sumário estatístico,
construção hierárquica para árvore visual e consulta JSONPath integrada.

Zero dependências de interface gráfica ou componentes visuais.
"""
import json
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Union
from wintoolbox.tools.data.json_path.logic import JsonPathMatch, query_jsonpath


def parse_json(raw_input: Union[str, bytes]) -> Tuple[bool, Any, str]:
    """
    Realiza o parse seguro de uma string ou bytes JSON.
    Retorna (sucesso, objeto_decodificado, mensagem_de_erro).
    """
    if isinstance(raw_input, bytes):
        try:
            raw_input = raw_input.decode("utf-8")
        except UnicodeDecodeError as exc:
            return False, None, f"Erro de codificação UTF-8: {exc}"

    cleaned = raw_input.strip()
    if not cleaned:
        return False, None, "Entrada JSON vazia."

    try:
        parsed = json.loads(cleaned)
        return True, parsed, ""
    except json.JSONDecodeError as exc:
        return False, None, f"Erro de sintaxe JSON na linha {exc.lineno}, coluna {exc.colno}: {exc.msg}"


def get_value_type_label(value: Any) -> str:
    """Retorna uma etiqueta legível para o tipo de dado JSON."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return f"array[{len(value)}]"
    if isinstance(value, dict):
        return f"object{{{len(value)}}}"
    return type(value).__name__


def calculate_statistics(data: Any) -> Dict[str, Any]:
    """
    Calcula métricas detalhadas sobre a estrutura JSON:
    - total_nodes
    - max_depth
    - type_counts (object, array, string, number, boolean, null)
    - total_keys
    """
    stats = {
        "total_nodes": 0,
        "max_depth": 1,
        "total_keys": 0,
        "type_counts": {
            "object": 0,
            "array": 0,
            "string": 0,
            "number": 0,
            "boolean": 0,
            "null": 0,
        },
    }

    def _traverse(node: Any, depth: int) -> None:
        stats["total_nodes"] += 1
        if depth > stats["max_depth"]:
            stats["max_depth"] = depth

        if node is None:
            stats["type_counts"]["null"] += 1
        elif isinstance(node, bool):
            stats["type_counts"]["boolean"] += 1
        elif isinstance(node, (int, float)):
            stats["type_counts"]["number"] += 1
        elif isinstance(node, str):
            stats["type_counts"]["string"] += 1
        elif isinstance(node, list):
            stats["type_counts"]["array"] += 1
            for item in node:
                _traverse(item, depth + 1)
        elif isinstance(node, dict):
            stats["type_counts"]["object"] += 1
            stats["total_keys"] += len(node)
            for val in node.values():
                _traverse(val, depth + 1)

    _traverse(data, 1)
    return stats


def search_nodes(
    data: Any,
    query: str,
    match_case: bool = False,
    max_results: int = 500,
) -> List[Dict[str, Any]]:
    """
    Busca nós na estrutura JSON por chave ou valor.
    Retorna lista de correspondências com caminho, chave, valor e tipo.
    """
    results: List[Dict[str, Any]] = []
    if not query:
        return results

    def _strip_accents(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    needle = query if match_case else _strip_accents(query.lower())

    def _matches(text: str) -> bool:
        target = text if match_case else _strip_accents(text.lower())
        return needle in target

    def _walk(node: Any, current_path: str) -> None:
        if len(results) >= max_results:
            return

        if isinstance(node, dict):
            for k, v in node.items():
                if len(results) >= max_results:
                    break
                k_path = f"{current_path}.{k}" if current_path else k
                # Casamento na chave
                if _matches(str(k)):
                    results.append({
                        "path": f"$.{k_path}",
                        "matched_on": "key",
                        "key": str(k),
                        "value": str(v)[:200],
                        "type": get_value_type_label(v),
                    })
                # Casamento no valor primitivo
                elif not isinstance(v, (dict, list)) and _matches(str(v)):
                    results.append({
                        "path": f"$.{k_path}",
                        "matched_on": "value",
                        "key": str(k),
                        "value": str(v),
                        "type": get_value_type_label(v),
                    })
                _walk(v, k_path)

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                if len(results) >= max_results:
                    break
                idx_path = f"{current_path}[{idx}]"
                if not isinstance(item, (dict, list)) and _matches(str(item)):
                    results.append({
                        "path": f"$.{idx_path}",
                        "matched_on": "value",
                        "key": f"[{idx}]",
                        "value": str(item),
                        "type": get_value_type_label(item),
                    })
                _walk(item, idx_path)

    _walk(data, "")
    return results


def query_by_jsonpath(data: Any, path_expression: str) -> List[Dict[str, Any]]:
    """
    Executa consulta JSONPath contra a estrutura de dados.
    """
    matches: List[JsonPathMatch] = query_jsonpath(data, path_expression)
    return [m.to_dict() for m in matches]
