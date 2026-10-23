"""
Persistência de configurações e preferências do usuário em JSON.
Localizado em %APPDATA%/WinToolbox/settings.json.
Suporta backup, restauração, favoritos e histórico de ferramentas recentes.
"""
import os
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",  # 'dark', 'light'
    "default_output_mode": "subfolder",  # 'subfolder', 'custom', 'same_folder'
    "default_subfolder_name": "convertidos",
    "default_conflict": "rename",  # 'rename', 'overwrite', 'skip'
    "default_recursive": False,    # Desmarcado por padrão conforme instrução
    "mirror_structure": True,
    "last_custom_dir": "",
    "minimize_to_tray": True,      # Minimizar para bandeja ao fechar
    "notifications_enabled": True, # Exibir notificações no Windows
    "global_hotkey_enabled": True, # Atalho global (Ctrl+Alt+T) para abrir a toolbox
    "favorites": [],               # IDs das ferramentas favoritas
    "recent_tools": []             # IDs das ferramentas usadas recentemente (máx 10)
}

def get_settings_dir() -> Path:
    """Retorna o diretório de dados da aplicação."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "WinToolbox"
    else:
        base = Path.home() / ".wintoolbox"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_settings_file() -> Path:
    return get_settings_dir() / "settings.json"

def load_settings() -> Dict[str, Any]:
    """Carrega as configurações salvas ou valores padrão."""
    f = get_settings_file()
    if not f.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            settings = dict(DEFAULT_SETTINGS)
            settings.update(data)
            return settings
    except Exception:
        return dict(DEFAULT_SETTINGS)

def save_settings(settings: Dict[str, Any]):
    """Salva as configurações atualizadas em disco."""
    f = get_settings_file()
    try:
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(settings, fp, indent=2, ensure_ascii=False)
    except Exception:
        pass

def add_recent_tool(tool_id: str):
    """Adiciona uma ferramenta ao topo da lista de recentes."""
    st = load_settings()
    recents = st.get("recent_tools", [])
    if tool_id in recents:
        recents.remove(tool_id)
    recents.insert(0, tool_id)
    st["recent_tools"] = recents[:10]  # Limita aos 10 mais recentes
    save_settings(st)

def toggle_favorite(tool_id: str) -> bool:
    """Alterna o status de favorito de uma ferramenta e retorna o novo estado."""
    st = load_settings()
    favs = st.get("favorites", [])
    if tool_id in favs:
        favs.remove(tool_id)
        is_fav = False
    else:
        favs.append(tool_id)
        is_fav = True
    st["favorites"] = favs
    save_settings(st)
    return is_fav

def is_favorite(tool_id: str) -> bool:
    """Verifica se uma ferramenta é favorita."""
    st = load_settings()
    return tool_id in st.get("favorites", [])

def export_settings(target_path: Path) -> bool:
    """Exporta o arquivo de configurações para backup."""
    src = get_settings_file()
    if not src.exists():
        save_settings(DEFAULT_SETTINGS)
    try:
        shutil.copy2(src, target_path)
        return True
    except Exception:
        return False

def import_settings(source_path: Path) -> bool:
    """Restaura as configurações a partir de um backup."""
    if not source_path.exists():
        return False
    try:
        with open(source_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            if not isinstance(data, dict):
                return False
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            save_settings(merged)
            return True
    except Exception:
        return False
