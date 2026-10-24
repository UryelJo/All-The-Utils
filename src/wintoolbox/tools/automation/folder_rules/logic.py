"""
Lógica pura do motor de regras automáticas para organização de arquivos e pastas.
Totalmente desacoplada de bibliotecas de interface visual.
"""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("automation.folder_rules")

DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "rule_docs",
        "name": "Mover Documentos e PDFs",
        "condition_type": "extension",
        "condition_value": ".pdf, .docx, .xlsx, .pptx, .txt, .csv",
        "action_type": "move",
        "destination": str(Path.home() / "Documents")
    },
    {
        "id": "rule_images",
        "name": "Mover Imagens e Fotos",
        "condition_type": "extension",
        "condition_value": ".png, .jpg, .jpeg, .webp, .gif, .svg",
        "action_type": "move",
        "destination": str(Path.home() / "Pictures")
    },
    {
        "id": "rule_installers",
        "name": "Mover Instaladores .exe e .msi",
        "condition_type": "extension",
        "condition_value": ".exe, .msi, .iso",
        "action_type": "move",
        "destination": str(Path.home() / "Downloads" / "Instaladores")
    }
]


def get_rules_storage_file() -> Path:
    """Retorna o caminho do arquivo de persistência das regras de automação."""
    app_dir = get_app_dir()
    p = app_dir / "automation" / "folder_rules.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_folder_rules() -> List[Dict[str, Any]]:
    """Carrega as regras salvas ou inicializa com as regras padrão."""
    f = get_rules_storage_file()
    if not f.exists():
        save_folder_rules(DEFAULT_RULES)
        return DEFAULT_RULES
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("Falha ao ler regras de pastas: %s", exc)
        return DEFAULT_RULES


def save_folder_rules(rules: List[Dict[str, Any]]) -> None:
    """Salva a lista de regras no disco."""
    f = get_rules_storage_file()
    f.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


def match_rule(file_path: Path, rule: Dict[str, Any]) -> bool:
    """Verifica se um arquivo atende aos critérios da regra."""
    cond_type = rule.get("condition_type", "extension")
    val = rule.get("condition_value", "").strip()

    if cond_type == "extension":
        # Lista de extensões separadas por vírgula
        exts = [e.strip().lower() for e in val.split(",") if e.strip()]
        # Garante ponto inicial
        exts_dotted = [e if e.startswith(".") else "." + e for e in exts]
        return file_path.suffix.lower() in exts_dotted

    elif cond_type == "keyword":
        keywords = [k.strip().lower() for k in val.split(",") if k.strip()]
        filename_lower = file_path.name.lower()
        return any(k in filename_lower for k in keywords)

    elif cond_type == "older_than_days":
        try:
            days = float(val)
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_days = (datetime.now() - mtime).total_seconds() / 86400.0
            return age_days >= days
        except Exception:
            return False

    elif cond_type == "size_greater_than_mb":
        try:
            size_mb = float(val)
            actual_mb = file_path.stat().st_size / (1024.0 * 1024.0)
            return actual_mb >= size_mb
        except Exception:
            return False

    return False


def evaluate_folder_rules(
    source_dir: Path,
    rules: List[Dict[str, Any]],
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Avalia e executa as regras sobre os arquivos contidos no diretório de origem.
    Retorna lista de ações executadas/simuladas.
    """
    if not source_dir.is_dir():
        raise ValueError(f"O diretório informado não existe: {source_dir}")

    results: List[Dict[str, Any]] = []

    for item in source_dir.iterdir():
        # Processa apenas arquivos normais
        if not item.is_file():
            continue

        for r in rules:
            if match_rule(item, r):
                action = r.get("action_type", "move")
                dest_str = r.get("destination", "").strip()
                dest_dir = Path(dest_str) if dest_str else None

                success = True
                message = ""

                if not dry_run:
                    try:
                        if action in ("move", "copy"):
                            if not dest_dir:
                                success = False
                                message = "Destino não especificado."
                            else:
                                dest_dir.mkdir(parents=True, exist_ok=True)
                                target_path = dest_dir / item.name
                                if target_path.exists():
                                    # Renomeia com sufixo se já existir
                                    target_path = dest_dir / f"{item.stem}_{int(datetime.now().timestamp())}{item.suffix}"

                                if action == "move":
                                    shutil.move(str(item), str(target_path))
                                    message = f"Movido para {dest_dir.name}"
                                else:
                                    shutil.copy2(str(item), str(target_path))
                                    message = f"Copiado para {dest_dir.name}"
                        elif action == "delete":
                            item.unlink()
                            message = "Arquivo excluído"
                    except Exception as exc:
                        success = False
                        message = f"Erro: {exc}"
                else:
                    message = f"Simulação: seria executada ação '{action}'"

                results.append({
                    "file_name": item.name,
                    "rule_name": r.get("name", "Regra"),
                    "action": action,
                    "destination": dest_str,
                    "success": success,
                    "message": message
                })
                # Uma vez que deu match na primeira regra, não aplica outras regras ao mesmo arquivo
                break

    return results
