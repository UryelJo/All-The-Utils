"""
Lógica pura para comparação semântica profunda de estruturas de dados (JSON, YAML, TOML).
Detecta adições, modificações e remoções ignorando formatação cosmética, espaços e ordem de chaves.

Zero dependências de interface gráfica ou widgets.
"""
import json
import tomllib
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None


def parse_structured_data(raw_text: str, format_hint: str = "auto") -> Tuple[bool, Any, str]:
    """
    Decodifica texto estruturado para objetos Python (dict, list, etc).
    Suporta JSON, YAML e TOML com detecção automática resiliente.
    """
    cleaned = raw_text.strip()
    if not cleaned:
        return False, None, "Entrada vazia."

    fmt = format_hint.lower()

    if fmt == "json" or (fmt == "auto" and (cleaned.startswith("{") or cleaned.startswith("["))):
        try:
            return True, json.loads(cleaned), "json"
        except Exception as exc:
            if fmt == "json":
                return False, None, f"Erro JSON: {exc}"

    if fmt == "toml":
        try:
            return True, tomllib.loads(cleaned), "toml"
        except Exception as exc:
            return False, None, f"Erro TOML: {exc}"

    if fmt == "yaml" or fmt == "auto":
        if yaml is not None:
            try:
                parsed = yaml.safe_load(cleaned)
                return True, parsed, "yaml"
            except Exception as exc:
                if fmt == "yaml":
                    return False, None, f"Erro YAML: {exc}"
        elif fmt == "yaml":
            return False, None, "Módulo PyYAML não disponível no ambiente."

    # Se auto falhou com JSON e YAML, tenta TOML
    if fmt == "auto":
        try:
            return True, tomllib.loads(cleaned), "toml"
        except Exception:
            pass

    # Tentativa final JSON
    try:
        return True, json.loads(cleaned), "json"
    except Exception as exc:
        return False, None, f"Formato não reconhecido ou erro de sintaxe: {exc}"


def diff_structures(
    obj_a: Any,
    obj_b: Any,
    current_path: str = "$",
) -> List[Dict[str, Any]]:
    """
    Compara recursivamente duas estruturas de dados e retorna uma lista de diferenças semânticas.
    Cada diferença possui: type ('added', 'removed', 'modified'), path, old_val, new_val.
    """
    diffs: List[Dict[str, Any]] = []

    # Se os tipos forem diferentes
    if type(obj_a) is not type(obj_b):
        diffs.append({
            "type": "modified",
            "path": current_path,
            "old_val": obj_a,
            "new_val": obj_b,
            "detail": f"Tipo alterado de {type(obj_a).__name__} para {type(obj_b).__name__}",
        })
        return diffs

    # Dicionários
    if isinstance(obj_a, dict):
        keys_a = set(obj_a.keys())
        keys_b = set(obj_b.keys())

        # Chaves removidas em B
        for k in sorted(keys_a - keys_b):
            k_path = f"{current_path}.{k}"
            diffs.append({
                "type": "removed",
                "path": k_path,
                "old_val": obj_a[k],
                "new_val": None,
                "detail": f"Chave '{k}' excluída",
            })

        # Chaves adicionadas em B
        for k in sorted(keys_b - keys_a):
            k_path = f"{current_path}.{k}"
            diffs.append({
                "type": "added",
                "path": k_path,
                "old_val": None,
                "new_val": obj_b[k],
                "detail": f"Chave '{k}' criada",
            })

        # Chaves comuns
        for k in sorted(keys_a & keys_b):
            k_path = f"{current_path}.{k}"
            sub_diffs = diff_structures(obj_a[k], obj_b[k], k_path)
            diffs.extend(sub_diffs)

    # Listas
    elif isinstance(obj_a, list):
        len_a = len(obj_a)
        len_b = len(obj_b)
        min_len = min(len_a, len_b)

        for i in range(min_len):
            idx_path = f"{current_path}[{i}]"
            sub_diffs = diff_structures(obj_a[i], obj_b[i], idx_path)
            diffs.extend(sub_diffs)

        # Itens extras em A (removidos)
        for i in range(min_len, len_a):
            idx_path = f"{current_path}[{i}]"
            diffs.append({
                "type": "removed",
                "path": idx_path,
                "old_val": obj_a[i],
                "new_val": None,
                "detail": f"Elemento do índice [{i}] removido",
            })

        # Itens extras em B (adicionados)
        for i in range(min_len, len_b):
            idx_path = f"{current_path}[{i}]"
            diffs.append({
                "type": "added",
                "path": idx_path,
                "old_val": None,
                "new_val": obj_b[i],
                "detail": f"Elemento no índice [{i}] adicionado",
            })

    # Valores escalares (str, int, float, bool, None)
    else:
        if obj_a != obj_b:
            diffs.append({
                "type": "modified",
                "path": current_path,
                "old_val": obj_a,
                "new_val": obj_b,
                "detail": f"Valor modificado de {repr(obj_a)} para {repr(obj_b)}",
            })

    return diffs


def summarize_diffs(diffs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Retorna sumário estatístico sobre as diferenças encontradas."""
    counts = {"added": 0, "removed": 0, "modified": 0}
    for d in diffs:
        t = d.get("type", "modified")
        if t in counts:
            counts[t] += 1

    return {
        "total_diffs": len(diffs),
        "is_identical": len(diffs) == 0,
        "added": counts["added"],
        "removed": counts["removed"],
        "modified": counts["modified"],
    }
