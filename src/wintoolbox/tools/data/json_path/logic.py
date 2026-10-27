"""
Lógica pura para avaliação e extração de expressões JSONPath (RFC 9535 / padrão JSONPath).
Suporta caminhos raiz ($), chaves filhas (.), descida recursiva (..),
curingas (*), índices numéricos [0], fatiamento [start:end] e expressões de filtro básicas [?(@.attr op val)].

Zero dependências de interface gráfica.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union


class JsonPathMatch:
    def __init__(self, path: str, value: Any):
        self.path = path
        self.value = value
        self.raw_value = value

    def to_dict(self) -> Dict[str, Any]:
        val_type = type(self.value).__name__
        val_str = json.dumps(self.value, ensure_ascii=False) if isinstance(self.value, (dict, list)) else str(self.value)
        return {
            "path": self.path,
            "type": val_type,
            "value": val_str,
            "raw_value": self.value,
        }


def _evaluate_filter(item: Any, filter_expr: str) -> bool:
    """
    Avalia predicados no formato [?(@.attr op val)] ou [?(@.attr)].
    Ex: @.price < 10, @.active == true, @.role != 'admin'
    """
    if not isinstance(item, dict):
        return False

    # Regex para operadores comuns: ==, !=, >=, <=, >, <
    m = re.match(r"@\.([a-zA-Z0-9_-]+)\s*(==|!=|>=|<=|>|<)\s*(.*)", filter_expr.strip())
    if not m:
        # Se for apenas teste de existência: @.attr
        m_exist = re.match(r"@\.([a-zA-Z0-9_-]+)", filter_expr.strip())
        if m_exist:
            attr = m_exist.group(1)
            return attr in item and bool(item[attr])
        return False

    attr, op, raw_val = m.group(1), m.group(2), m.group(3).strip()
    if attr not in item:
        return False

    item_val = item[attr]

    # Converte raw_val para tipo do item_val se possível
    try:
        if raw_val.lower() == "true":
            target_val: Any = True
        elif raw_val.lower() == "false":
            target_val = False
        elif raw_val.lower() == "null" or raw_val.lower() == "none":
            target_val = None
        elif (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
            target_val = raw_val[1:-1]
        elif "." in raw_val:
            target_val = float(raw_val)
        else:
            target_val = int(raw_val)
    except Exception:
        target_val = raw_val

    try:
        if op == "==":
            return item_val == target_val
        elif op == "!=":
            return item_val != target_val
        elif op == ">":
            return float(item_val) > float(target_val)
        elif op == ">=":
            return float(item_val) >= float(target_val)
        elif op == "<":
            return float(item_val) < float(target_val)
        elif op == "<=":
            return float(item_val) <= float(target_val)
    except Exception:
        return False

    return False


def query_jsonpath(data: Any, expression: str) -> List[JsonPathMatch]:
    """
    Executa a consulta JSONPath sobre os dados Python (dict ou list) e retorna a lista de nós encontrados.
    """
    expr = expression.strip()
    if not expr:
        return []

    if expr.startswith("$"):
        expr = expr[1:]
    if expr.startswith(".") and not expr.startswith(".."):
        expr = expr[1:]

    # Parser recursivo passo a passo
    results: List[Tuple[str, Any]] = [("$", data)]

    # Tokenização de segmentos de caminho
    tokens = _tokenize_jsonpath(expr)

    for token_type, token_val in tokens:
        new_results: List[Tuple[str, Any]] = []

        for curr_path, curr_val in results:
            if token_type == "recursive":
                # Descendente recursivo: busca todas as chaves correspondentes na sub-árvore
                sub_matches = _collect_recursive(curr_val, token_val, curr_path)
                new_results.extend(sub_matches)

            elif token_type == "key":
                if isinstance(curr_val, dict) and token_val in curr_val:
                    new_results.append((f"{curr_path}['{token_val}']", curr_val[token_val]))

            elif token_type == "wildcard":
                if isinstance(curr_val, dict):
                    for k, v in curr_val.items():
                        new_results.append((f"{curr_path}['{k}']", v))
                elif isinstance(curr_val, list):
                    for idx, item in enumerate(curr_val):
                        new_results.append((f"{curr_path}[{idx}]", item))

            elif token_type == "index":
                idx = int(token_val)
                if isinstance(curr_val, list) and -len(curr_val) <= idx < len(curr_val):
                    real_idx = idx if idx >= 0 else len(curr_val) + idx
                    new_results.append((f"{curr_path}[{real_idx}]", curr_val[idx]))

            elif token_type == "slice":
                if isinstance(curr_val, list):
                    start, stop, step = token_val
                    sliced_items = list(enumerate(curr_val))[slice(start, stop, step)]
                    for real_idx, item in sliced_items:
                        new_results.append((f"{curr_path}[{real_idx}]", item))

            elif token_type == "filter":
                if isinstance(curr_val, list):
                    for idx, item in enumerate(curr_val):
                        if _evaluate_filter(item, token_val):
                            new_results.append((f"{curr_path}[{idx}]", item))

        results = new_results

    return [JsonPathMatch(p, v) for p, v in results]


def _tokenize_jsonpath(expr: str) -> List[Tuple[str, Any]]:
    """
    Converte uma expressão JSONPath em uma sequência de tokens.
    """
    tokens: List[Tuple[str, Any]] = []
    i = 0
    n = len(expr)

    while i < n:
        # Descendente recursivo: ..key ou ..*
        if expr[i:i+2] == "..":
            i += 2
            # Pega o nome da chave ou *
            m = re.match(r"([a-zA-Z0-9_-]+|\*)", expr[i:])
            if m:
                target = m.group(1)
                tokens.append(("recursive", target))
                i += len(target)
            continue

        # Curinga puro após ponto
        if expr[i] == "*":
            tokens.append(("wildcard", "*"))
            i += 1
            continue

        # Ponto normal
        if expr[i] == ".":
            i += 1
            continue

        # Colchetes: [*], [0], [start:end], [?(@...)], ['key']
        if expr[i] == "[":
            end_bracket = expr.find("]", i)
            if end_bracket == -1:
                break
            content = expr[i+1:end_bracket].strip()
            i = end_bracket + 1

            if content == "*":
                tokens.append(("wildcard", "*"))
            elif content.startswith("?(") and content.endswith(")"):
                filter_body = content[2:-1]
                tokens.append(("filter", filter_body))
            elif ":" in content:
                # Slice: start:stop:step
                parts = content.split(":")
                start = int(parts[0]) if parts[0] else None
                stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
                step = int(parts[2]) if len(parts) > 2 and parts[2] else None
                tokens.append(("slice", (start, stop, step)))
            elif (content.startswith("'") and content.endswith("'")) or (content.startswith('"') and content.endswith('"')):
                tokens.append(("key", content[1:-1]))
            elif content.lstrip("-").isdigit():
                tokens.append(("index", int(content)))
            continue

        # Chave alfanumérica normal
        m = re.match(r"([a-zA-Z0-9_-]+)", expr[i:])
        if m:
            key_name = m.group(1)
            tokens.append(("key", key_name))
            i += len(key_name)
            continue

        i += 1

    return tokens


def _collect_recursive(val: Any, target_key: str, curr_path: str) -> List[Tuple[str, Any]]:
    """
    Coleta todas as ocorrências de `target_key` recursivamente na estrutura.
    """
    matches = []
    if isinstance(val, dict):
        for k, v in val.items():
            child_path = f"{curr_path}['{k}']"
            if target_key == "*" or k == target_key:
                matches.append((child_path, v))
            matches.extend(_collect_recursive(v, target_key, child_path))
    elif isinstance(val, list):
        for idx, item in enumerate(val):
            child_path = f"{curr_path}[{idx}]"
            matches.extend(_collect_recursive(item, target_key, child_path))
    return matches


SAMPLE_JSON = {
    "store": {
        "name": "Livraria WinToolbox",
        "book": [
            {
                "category": "ficcao",
                "author": "J. R. R. Tolkien",
                "title": "O Senhor dos Anéis",
                "price": 89.90,
                "in_stock": True,
            },
            {
                "category": "tecnologia",
                "author": "Guido van Rossum",
                "title": "Python Avançado e Arquitetura",
                "price": 54.00,
                "in_stock": True,
            },
            {
                "category": "tecnologia",
                "author": "Martin Fowler",
                "title": "Refatoração e Design Patterns",
                "price": 120.00,
                "in_stock": False,
            },
            {
                "category": "ficcao",
                "author": "Isaac Asimov",
                "title": "Fundação",
                "price": 42.50,
                "in_stock": True,
            },
        ],
        "bicycle": {
            "color": "vermelha",
            "price": 350.00,
        },
    }
}
