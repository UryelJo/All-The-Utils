"""
Persistência de configurações e preferências do usuário em JSON.
Localizado em %APPDATA%/WinToolbox/settings.json
"""
import os
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",  # 'dark', 'light', 'system'
    "default_output_mode": "subfolder",  # 'subfolder', 'custom', 'same_folder'
    "default_subfolder_name": "convertidos",
    "default_conflict": "rename",  # 'rename', 'overwrite', 'skip'
    "default_recursive": False,    # Desmarcado por padrão conforme instrução
    "mirror_structure": True,
    "last_custom_dir": "",
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
