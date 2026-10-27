"""
Lógica pura para comparação e auditoria diferencial de arquivos de ambiente (.env vs .env.example).
Detecta chaves ausentes, variáveis vazias, novos parâmetros e mascara segredos sensíveis.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SENSITIVE_KEY_PATTERNS = [
    r'secret', r'password', r'passwd', r'token', r'key', r'auth',
    r'private', r'api_?key', r'cred', r'database_url', r'connection_string'
]


@dataclass
class EnvDiffItem:
    """Item de comparação entre template e arquivo real de ambiente."""
    key: str
    status: str  # "missing_in_target", "missing_in_template", "empty_in_target", "matched"
    template_value: str
    target_value: str
    is_secret: bool


def is_sensitive_key(key: str) -> bool:
    """Verifica se a chave corresponde a padrões de segredos criptográficos ou credenciais."""
    key_lower = key.lower()
    for pat in SENSITIVE_KEY_PATTERNS:
        if re.search(pat, key_lower):
            return True
    return False


def mask_value(val: str, is_secret: bool = True) -> str:
    """Mascara o valor de segredos para exibição segura."""
    if not is_secret or not val:
        return val

    val_len = len(val)
    if val_len <= 4:
        return "••••"
    if val_len <= 8:
        return f"{val[:1]}••••{val[-1:]}"
    return f"{val[:2]}••••••••{val[-2:]}"


def parse_env_file(file_path: Path) -> Dict[str, str]:
    """Interpreta um arquivo .env retornando dicionário de chaves e valores."""
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo .env não encontrado: {file_path}")

    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue

    env_dict: Dict[str, str] = {}
    lines = content.splitlines()

    for line in lines:
        line_clean = line.strip()
        # Ignora linhas vazias ou comentários completos
        if not line_clean or line_clean.startswith("#"):
            continue

        # Separa na primeira ocorrência de '='
        if "=" in line_clean:
            key, val = line_clean.split("=", 1)
            key = key.strip()
            # Remove "export " se houver
            if key.startswith("export "):
                key = key[7:].strip()

            val = val.strip()

            # Trata aspas com comentários inline subsequentes
            if (val.startswith('"') and '"' in val[1:]) or (val.startswith("'") and "'" in val[1:]):
                quote_char = val[0]
                closing_idx = val.find(quote_char, 1)
                val = val[1:closing_idx]
            else:
                if " #" in val:
                    val = val.split(" #", 1)[0].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]

            env_dict[key] = val

    return env_dict


def compare_env_files(
    template_path: Path,
    target_path: Path,
    mask_secrets: bool = True
) -> List[EnvDiffItem]:
    """
    Compara o arquivo modelo (template) contra o arquivo real de produção/desenvolvimento (target).
    """
    template_env = parse_env_file(template_path)
    target_env = parse_env_file(target_path)

    all_keys = set(template_env.keys()).union(set(target_env.keys()))
    sorted_keys = sorted(all_keys)

    results: List[EnvDiffItem] = []

    for k in sorted_keys:
        secret = is_sensitive_key(k)
        in_template = k in template_env
        in_target = k in target_env

        t_val = template_env.get(k, "")
        target_val = target_env.get(k, "")

        if not in_target:
            status = "missing_in_target"
        elif not in_template:
            status = "missing_in_template"
        elif in_target and not target_val.strip() and t_val.strip():
            status = "empty_in_target"
        else:
            status = "matched"

        display_t_val = mask_value(t_val, secret) if mask_secrets else t_val
        display_target_val = mask_value(target_val, secret) if mask_secrets else target_val

        results.append(
            EnvDiffItem(
                key=k,
                status=status,
                template_value=display_t_val,
                target_value=display_target_val,
                is_secret=secret
            )
        )

    # Ordena: Primeiro os ausentes, depois vazios, depois não-documentados, por fim matched
    priority = {
        "missing_in_target": 0,
        "empty_in_target": 1,
        "missing_in_template": 2,
        "matched": 3
    }
    results.sort(key=lambda x: (priority.get(x.status, 9), x.key))
    return results


def generate_missing_env_snippet(
    diff_items: List[EnvDiffItem],
    unmasked_template: Optional[Dict[str, str]] = None
) -> str:
    """Gera um trecho de texto com todas as variáveis que estão ausentes no arquivo alvo."""
    missing = [i for i in diff_items if i.status in ["missing_in_target", "empty_in_target"]]
    if not missing:
        return ""

    lines = ["# Variáveis geradas automaticamente pelo Comparador de Ambientes do WinToolbox"]
    for item in missing:
        val = item.template_value
        if unmasked_template and item.key in unmasked_template:
            val = unmasked_template[item.key]
        lines.append(f"{item.key}={val}")

    return "\n".join(lines)
