"""
Lógica pura de execução e gerenciamento de scripts locais (.bat, .ps1, .py, .cmd, .vbs).
Totalmente isolada de bibliotecas gráficas.
"""
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("automation.script_runner")


def get_scripts_storage_file() -> Path:
    """Retorna o caminho do arquivo de persistência dos scripts salvos."""
    app_dir = get_app_dir()
    p = app_dir / "automation" / "saved_scripts.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_saved_scripts() -> List[Dict[str, Any]]:
    """Carrega a lista de scripts configurados pelo usuário."""
    f = get_scripts_storage_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("Falha ao carregar scripts salvos: %s", exc)
        return []


def save_scripts_list(scripts: List[Dict[str, Any]]) -> None:
    """Salva a lista atualizada de scripts."""
    f = get_scripts_storage_file()
    f.write_text(json.dumps(scripts, indent=2, ensure_ascii=False), encoding="utf-8")


def add_or_update_script_entry(
    name: str,
    script_path: str,
    args: str = "",
    work_dir: str = ""
) -> Dict[str, Any]:
    """Cadastra ou atualiza uma entrada de script."""
    scripts = load_saved_scripts()
    entry = {
        "id": int(Path(script_path).stat().st_mtime) if Path(script_path).exists() else len(scripts) + 1,
        "name": name.strip() or Path(script_path).stem,
        "path": script_path.strip(),
        "args": args.strip(),
        "work_dir": work_dir.strip() or str(Path(script_path).parent)
    }

    # Atualiza se já existir pelo path
    updated = False
    for i, s in enumerate(scripts):
        if s["path"] == entry["path"]:
            scripts[i] = entry
            updated = True
            break
    if not updated:
        scripts.append(entry)

    save_scripts_list(scripts)
    return entry


def delete_script_entry(script_path: str) -> bool:
    """Remove um script salvo pelo caminho."""
    scripts = load_saved_scripts()
    new_scripts = [s for s in scripts if s["path"] != script_path]
    if len(new_scripts) != len(scripts):
        save_scripts_list(new_scripts)
        return True
    return False


def build_script_command(script_path: str, args_str: str = "") -> List[str]:
    """
    Constrói a lista de comando e argumentos apropriada conforme a extensão do arquivo.
    """
    p = Path(script_path.strip())
    ext = p.suffix.lower()
    user_args = args_str.strip().split() if args_str.strip() else []

    if ext == ".ps1":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(p)] + user_args
    elif ext in (".py", ".pyw"):
        return [sys.executable, str(p)] + user_args
    elif ext in (".bat", ".cmd"):
        return ["cmd.exe", "/c", str(p)] + user_args
    elif ext == ".vbs":
        return ["cscript.exe", "//nologo", str(p)] + user_args
    else:
        # Execução direta padrão
        return [str(p)] + user_args
