"""
Lógica pura para conversão universal bidirecional entre formatos de arquivos de configuração:
.env, .ini, .properties, TOML, YAML e JSON. Suporta achatamento (flatten) e aninhamento (unflatten).

Zero dependências de interface gráfica ou widgets.
"""
import configparser
import io
import json
import re
import tomllib
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """
    Achata um dicionário aninhado em chaves únicas com notação de ponto.
    Ex: {"db": {"host": "localhost"}} -> {"db.host": "localhost"}
    """
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
    """
    Expande chaves pontilhadas em um dicionário hierárquico aninhado.
    Ex: {"db.host": "localhost"} -> {"db": {"host": "localhost"}}
    """
    result: Dict[str, Any] = {}
    for key, value in d.items():
        parts = key.split(sep)
        curr = result
        for part in parts[:-1]:
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        curr[parts[-1]] = value
    return result


def parse_env(text: str) -> Dict[str, str]:
    """Decodifica conteúdo no formato .env."""
    data: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Remove aspas envolventes se houver
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            data[k] = v
    return data


def serialize_env(data: Dict[str, Any]) -> str:
    """Serializa dicionário no formato .env."""
    flat = flatten_dict(data, sep="_")
    lines = []
    for k, v in flat.items():
        clean_k = re.sub(r"[^a-zA-Z0-9_]", "_", str(k)).upper()
        str_v = str(v)
        if any(c in str_v for c in (' ', '"', "'", '\n', '$')):
            escaped = str_v.replace('"', '\\"')
            lines.append(f'{clean_k}="{escaped}"')
        else:
            lines.append(f'{clean_k}={str_v}')
    return "\n".join(lines) + "\n"


def parse_ini(text: str) -> Dict[str, Any]:
    """Decodifica conteúdo no formato .ini."""
    cp = configparser.ConfigParser()
    try:
        cp.read_string(text)
    except configparser.MissingSectionHeaderError:
        # Se não tiver cabeçalho de seção, injeta seção [DEFAULT]
        cp.read_string(f"[DEFAULT]\n{text}")

    result: Dict[str, Any] = {}
    for section in cp.sections():
        result[section] = dict(cp[section])

    if cp.defaults():
        if "DEFAULT" in result:
            result["DEFAULT"].update(dict(cp.defaults()))
        else:
            result["DEFAULT"] = dict(cp.defaults())

    return result


def serialize_ini(data: Dict[str, Any]) -> str:
    """Serializa dados para o formato .ini."""
    cp = configparser.ConfigParser()
    has_subdicts = any(isinstance(v, dict) for v in data.values())

    if not has_subdicts:
        cp["DEFAULT"] = {str(k): str(v) for k, v in data.items()}
    else:
        for sec_name, sec_val in data.items():
            if isinstance(sec_val, dict):
                cp[str(sec_name)] = {str(k): str(v) for k, v in sec_val.items()}
            else:
                if "DEFAULT" not in cp:
                    cp["DEFAULT"] = {}
                cp["DEFAULT"][str(sec_name)] = str(sec_val)

    out = io.StringIO()
    cp.write(out)
    return out.getvalue()


def parse_properties(text: str) -> Dict[str, str]:
    """Decodifica arquivo no formato Java .properties."""
    data: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        # Delimitador pode ser = ou :
        m = re.split(r"[=:]", line, maxsplit=1)
        if len(m) == 2:
            data[m[0].strip()] = m[1].strip()
        elif len(m) == 1:
            data[m[0].strip()] = ""
    return data


def serialize_properties(data: Dict[str, Any]) -> str:
    """Serializa dicionário para formato Java .properties."""
    flat = flatten_dict(data, sep=".")
    lines = [f"{k}={v}" for k, v in flat.items()]
    return "\n".join(lines) + "\n"


def parse_config_content(text: str, source_format: str) -> Tuple[bool, Any, str]:
    """
    Realiza o parse do texto de configuração de acordo com o formato fornecido:
    'env', 'ini', 'properties', 'toml', 'yaml', 'json'.
    """
    cleaned = text.strip()
    if not cleaned:
        return False, None, "Entrada vazia."

    fmt = source_format.lower()
    try:
        if fmt == "env":
            return True, parse_env(cleaned), ""
        elif fmt == "ini":
            return True, parse_ini(cleaned), ""
        elif fmt == "properties":
            return True, parse_properties(cleaned), ""
        elif fmt == "toml":
            return True, tomllib.loads(cleaned), ""
        elif fmt == "yaml":
            if yaml is None:
                return False, None, "PyYAML não está instalado."
            return True, yaml.safe_load(cleaned), ""
        elif fmt == "json":
            return True, json.loads(cleaned), ""
        else:
            return False, None, f"Formato de origem desconhecido: '{source_format}'."
    except Exception as exc:
        return False, None, f"Erro ao decodificar {fmt.upper()}: {exc}"


def serialize_config_content(
    data: Any,
    target_format: str,
    flatten: bool = False,
) -> Tuple[bool, str, str]:
    """
    Serializa dados Python para o formato de configuração desejado.
    """
    fmt = target_format.lower()
    work_data = data
    if isinstance(data, dict):
        if flatten:
            work_data = flatten_dict(data)
        else:
            # Se for formato que suporta aninhamento, tenta unflatten se tiver chaves pontilhadas
            if fmt in ("json", "yaml", "toml") and any("." in str(k) for k in data.keys()):
                work_data = unflatten_dict(data)

    try:
        if fmt == "env":
            if not isinstance(work_data, dict):
                return False, "", "O formato .env exige um mapeamento chave-valor."
            return True, serialize_env(work_data), ""

        elif fmt == "ini":
            if not isinstance(work_data, dict):
                return False, "", "O formato .ini exige um mapeamento chave-valor ou seções."
            return True, serialize_ini(work_data), ""

        elif fmt == "properties":
            if not isinstance(work_data, dict):
                return False, "", "O formato .properties exige um mapeamento chave-valor."
            return True, serialize_properties(work_data), ""

        elif fmt == "toml":
            if not isinstance(work_data, dict):
                return False, "", "TOML exige um dicionário raiz."
            # Serializador TOML simples para compatibilidade
            lines = []
            tables = []
            for k, v in work_data.items():
                if isinstance(v, dict):
                    tables.append((k, v))
                elif isinstance(v, (int, float, bool)):
                    lines.append(f"{k} = {str(v).lower() if isinstance(v, bool) else v}")
                elif isinstance(v, list):
                    lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
                else:
                    lines.append(f'{k} = "{str(v)}"')

            for sec, sec_dict in tables:
                lines.append(f"\n[{sec}]")
                for sk, sv in sec_dict.items():
                    if isinstance(sv, (int, float, bool)):
                        lines.append(f"{sk} = {str(sv).lower() if isinstance(sv, bool) else sv}")
                    elif isinstance(sv, list):
                        lines.append(f"{sk} = {json.dumps(sv, ensure_ascii=False)}")
                    else:
                        lines.append(f'{sk} = "{str(sv)}"')

            return True, "\n".join(lines) + "\n", ""

        elif fmt == "yaml":
            if yaml is None:
                return False, "", "PyYAML não está instalado."
            return True, yaml.safe_dump(work_data, sort_keys=False, allow_unicode=True), ""

        elif fmt == "json":
            return True, json.dumps(work_data, indent=2, ensure_ascii=False) + "\n", ""

        else:
            return False, "", f"Formato de destino desconhecido: '{target_format}'."
    except Exception as exc:
        return False, "", f"Erro ao serializar para {fmt.upper()}: {exc}"
