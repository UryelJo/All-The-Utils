"""
Persistência de configurações e preferências do usuário em JSON.
Localizado em %APPDATA%/WinToolbox/settings.json.
Suporta backup, restauração, favoritos e histórico de ferramentas recentes.
"""
import os
import sys
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",  # 'dark', 'light', 'system'
    "accent_override": "",  # Vazio = cor do Windows (DWM), ou HEX ex: '#0078d4'
    "sidebar_collapsed": False,
    "home_layout": {
        "show_smart_drop": False,
        "show_system_health": False,
        "show_favorites_recents": True,
        "card_density": "comfortable",
        "startup_view": "home",         # 'home' | 'last_tool'
        "last_opened_tool": "",
    },
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
    "recent_tools": [],            # IDs das ferramentas usadas recentemente (máx 10)
    "api_tokens": {}               # Tokens e chaves de API centralizados { "servico": "token" }
}

def is_portable_mode() -> bool:
    """Detecta se o aplicativo está rodando em modo portátil (pasta 'data' ou arquivo '.portable' ao lado do app)."""
    app_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
    return (app_root / ".portable").exists() or (app_root / "data").is_dir()


def get_settings_dir() -> Path:
    """Retorna o diretório de dados da aplicação.
    Suporta Modo Portátil automático (sem gravar em %APPDATA% se existir 'data' ou '.portable' localmente).
    """
    app_root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
    portable_data_dir = app_root / "data"
    portable_flag = app_root / ".portable"
    if portable_flag.exists() or portable_data_dir.is_dir():
        portable_data_dir.mkdir(parents=True, exist_ok=True)
        return portable_data_dir

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "AllTheUtils"
        legacy = Path(appdata) / "WinToolbox"
        if not base.exists() and legacy.exists():
            try:
                shutil.copytree(legacy, base)
            except Exception:
                pass
    else:
        base = Path.home() / ".alltheutils"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_app_dir() -> Path:
    """Retorna o diretório base de dados da aplicação."""
    return get_settings_dir()


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
    hl = dict(DEFAULT_SETTINGS["home_layout"])
    if isinstance(st.get("home_layout"), dict):
        hl.update(st["home_layout"])
    hl["last_opened_tool"] = tool_id
    st["home_layout"] = hl
    save_settings(st)


def get_home_layout() -> Dict[str, Any]:
    """Retorna as preferências de personalização da tela inicial com fallback seguro."""
    st = load_settings()
    layout = dict(DEFAULT_SETTINGS["home_layout"])
    saved = st.get("home_layout")
    if isinstance(saved, dict):
        layout.update(saved)
    return layout


def update_home_layout(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza e persiste as preferências de personalização da tela inicial."""
    st = load_settings()
    layout = get_home_layout()
    layout.update(updates)
    st["home_layout"] = layout
    save_settings(st)
    return layout

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

def add_favorite_tool(tool_id: str):
    """Adiciona uma ferramenta aos favoritos."""
    st = load_settings()
    favs = st.get("favorites", [])
    if tool_id not in favs:
        favs.append(tool_id)
        st["favorites"] = favs
        save_settings(st)

def remove_favorite_tool(tool_id: str):
    """Remove uma ferramenta dos favoritos."""
    st = load_settings()
    favs = st.get("favorites", [])
    if tool_id in favs:
        favs.remove(tool_id)
        st["favorites"] = favs
        save_settings(st)

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

def get_api_token(service_id: str, default: str = "") -> str:
    """Obtém o token ou chave de API configurada para um serviço específico."""
    st = load_settings()
    tokens = st.get("api_tokens", {})
    return tokens.get(service_id.lower().strip(), default)

def set_api_token(service_id: str, token_value: str) -> None:
    """Salva ou remove a chave de API de um serviço."""
    st = load_settings()
    tokens = st.get("api_tokens", {})
    clean_key = service_id.lower().strip()
    clean_val = token_value.strip()

    if clean_val:
        tokens[clean_key] = clean_val
    else:
        tokens.pop(clean_key, None)

    st["api_tokens"] = tokens
    save_settings(st)

def get_all_api_tokens() -> Dict[str, str]:
    """Retorna todas as chaves de API cadastradas."""
    st = load_settings()
    return dict(st.get("api_tokens", {}))

