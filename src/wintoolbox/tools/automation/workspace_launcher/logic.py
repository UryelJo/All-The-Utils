"""
Lógica pura de lançamento de ambientes de trabalho (Workspaces).
Abre lotes de aplicativos, pastas e URLs no navegador padrão em 1 clique.
Isolada de bibliotecas de interface visual.
"""
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.settings import get_app_dir

_log = get_logger("automation.workspace_launcher")

DEFAULT_WORKSPACES: List[Dict[str, Any]] = [
    {
        "id": "dev_web",
        "name": "Desenvolvimento Web",
        "description": "Inicia ambiente de desenvolvimento frontend e referências",
        "items": [
            {"type": "url", "target": "https://github.com"},
            {"type": "url", "target": "https://stackoverflow.com"},
            {"type": "url", "target": "http://localhost:3000"}
        ]
    },
    {
        "id": "estudos",
        "name": "Estudos e Pesquisa",
        "description": "Portais de documentação e anotações",
        "items": [
            {"type": "url", "target": "https://wikipedia.org"},
            {"type": "url", "target": "https://devdocs.io"}
        ]
    }
]


def get_workspaces_file() -> Path:
    """Retorna o caminho do arquivo de persistência de workspaces."""
    app_dir = get_app_dir()
    p = app_dir / "automation" / "workspaces.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_workspaces() -> List[Dict[str, Any]]:
    """Carrega todos os workspaces salvos ou inicializa com os padrões."""
    f = get_workspaces_file()
    if not f.exists():
        save_workspaces(DEFAULT_WORKSPACES)
        return DEFAULT_WORKSPACES
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("Falha ao ler workspaces: %s", exc)
        return DEFAULT_WORKSPACES


def save_workspaces(workspaces: List[Dict[str, Any]]) -> None:
    """Persiste a lista de workspaces no disco."""
    f = get_workspaces_file()
    f.write_text(json.dumps(workspaces, indent=2, ensure_ascii=False), encoding="utf-8")


def launch_single_item(item_type: str, target: str) -> Tuple[bool, str]:
    """Abre um único item (URL, executável ou pasta) no Windows."""
    t = target.strip()
    if not t:
        return False, "Alvo vazio"

    try:
        if item_type == "url":
            if not t.startswith(("http://", "https://")):
                t = "https://" + t
            os.startfile(t)
            return True, f"URL aberta no navegador: {t}"
        elif item_type == "folder":
            p = Path(t)
            if p.is_dir():
                os.startfile(str(p))
                return True, f"Pasta aberta no Explorer: {p}"
            return False, f"Pasta não encontrada: {t}"
        else:  # app / executável
            p = Path(t)
            if p.is_file():
                os.startfile(str(p))
                return True, f"Aplicativo iniciado: {p.name}"
            else:
                # Tenta executar pelo PATH do sistema
                subprocess.Popen(t, shell=True)
                return True, f"Comando disparado: {t}"
    except Exception as exc:
        _log.warning("Falha ao abrir item '%s': %s", t, exc)
        return False, f"Erro ao abrir {t}: {exc}"


def launch_workspace(workspace: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Dispara todos os itens do workspace em lote."""
    results: List[Tuple[str, bool, str]] = []
    items = workspace.get("items", [])

    for item in items:
        itype = item.get("type", "url")
        itarget = item.get("target", "")
        success, msg = launch_single_item(itype, itarget)
        results.append((itarget, success, msg))

    return results
