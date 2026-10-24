"""
Lógica pura de gerenciamento de pacotes do Windows via Windows Package Manager (winget).
Totalmente isolada de bibliotecas de interface visual.
"""
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.winget")

CURATED_APPS: List[Dict[str, str]] = [
    # Navegadores
    {"id": "Google.Chrome", "name": "Google Chrome", "category": "Navegadores"},
    {"id": "Mozilla.Firefox", "name": "Mozilla Firefox", "category": "Navegadores"},
    {"id": "Brave.Brave", "name": "Brave Browser", "category": "Navegadores"},
    # Utilitários e Compactação
    {"id": "7zip.7zip", "name": "7-Zip", "category": "Utilitários"},
    {"id": "RARLab.WinRAR", "name": "WinRAR", "category": "Utilitários"},
    {"id": "VideoLAN.VLC", "name": "VLC Media Player", "category": "Mídia"},
    {"id": "Spotify.Spotify", "name": "Spotify", "category": "Mídia"},
    {"id": "OBSProject.OBSStudio", "name": "OBS Studio", "category": "Mídia"},
    # Desenvolvimento
    {"id": "Microsoft.VisualStudioCode", "name": "Visual Studio Code", "category": "Desenvolvimento"},
    {"id": "Git.Git", "name": "Git for Windows", "category": "Desenvolvimento"},
    {"id": "Python.Python.3.12", "name": "Python 3.12", "category": "Desenvolvimento"},
    {"id": "OpenJS.NodeJS", "name": "Node.js (LTS)", "category": "Desenvolvimento"},
    {"id": "Docker.DockerDesktop", "name": "Docker Desktop", "category": "Desenvolvimento"},
    # Comunicação e Produtividade
    {"id": "Discord.Discord", "name": "Discord", "category": "Comunicação"},
    {"id": "Telegram.TelegramDesktop", "name": "Telegram Desktop", "category": "Comunicação"},
    {"id": "WhatsApp.WhatsApp", "name": "WhatsApp", "category": "Comunicação"},
    {"id": "Notion.Notion", "name": "Notion", "category": "Produtividade"},
    {"id": "Obsidian.Obsidian", "name": "Obsidian", "category": "Produtividade"}
]


def is_winget_installed() -> bool:
    """Verifica se o comando winget está acessível no PATH do sistema."""
    return shutil.which("winget.exe") is not None or shutil.which("winget") is not None


def get_curated_apps() -> List[Dict[str, str]]:
    """Retorna o catálogo curado de aplicativos populares."""
    return list(CURATED_APPS)


def parse_winget_upgrade_output(raw_output: str) -> List[Dict[str, str]]:
    """
    Interpreta a saída em texto do comando 'winget upgrade'
    e extrai os softwares que possuem atualização disponível.
    """
    upgrades: List[Dict[str, str]] = []
    lines = raw_output.splitlines()

    # Procura linha de cabeçalho delimitadora (geralmente com traços ------ )
    header_idx = -1
    for i, line in enumerate(lines):
        if "---" in line:
            header_idx = i
            break

    if header_idx != -1 and header_idx + 1 < len(lines):
        data_lines = lines[header_idx + 1:]
    else:
        data_lines = lines

    for line in data_lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("<") or "upgrades available" in line_str.lower():
            continue

        parts = re.split(r"\s{2,}", line_str)
        if len(parts) >= 3:
            name = parts[0].strip()
            app_id = parts[1].strip()
            curr_ver = parts[2].strip() if len(parts) > 2 else ""
            new_ver = parts[3].strip() if len(parts) > 3 else ""

            # Filtra linhas irrelevantes
            if app_id and "." in app_id:
                upgrades.append({
                    "name": name,
                    "id": app_id,
                    "current_version": curr_ver,
                    "available_version": new_ver
                })

    return upgrades


def list_available_upgrades() -> List[Dict[str, str]]:
    """Executa 'winget upgrade' e retorna os programas com novas versões."""
    if not is_winget_installed():
        return []

    try:
        proc = subprocess.run(
            ["winget", "upgrade", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=45
        )
        return parse_winget_upgrade_output(proc.stdout)
    except Exception as exc:
        _log.warning("Falha ao consultar atualizações via winget: %s", exc)
        return []


def build_install_command(app_id: str) -> List[str]:
    """Gera a lista de comando para instalação silenciosa de um pacote."""
    return ["winget", "install", "--id", app_id.strip(), "--exact", "--accept-source-agreements", "--accept-package-agreements"]


def build_upgrade_command(app_id: str) -> List[str]:
    """Gera o comando de atualização para um pacote específico."""
    return ["winget", "upgrade", "--id", app_id.strip(), "--exact", "--accept-source-agreements", "--accept-package-agreements"]


def build_upgrade_all_command() -> List[str]:
    """Gera o comando para atualizar todos os programas do sistema de uma vez."""
    return ["winget", "upgrade", "--all", "--include-unknown", "--accept-source-agreements", "--accept-package-agreements"]
