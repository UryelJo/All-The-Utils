"""
Lógica pura para gerenciamento e persistência de atalhos globais de teclado no Windows.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Dict, List, Optional, Tuple

# Constantes de modificadores Win32 para RegisterHotKey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Mapeamento básico de teclas virtuais (VK Codes)
VK_MAP = {
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45, "F": 0x46, "G": 0x47,
    "H": 0x48, "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E,
    "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54, "U": 0x55,
    "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "ESCAPE": 0x1B,
}


@dataclass
class GlobalHotkey:
    """Representa um atalho de teclado global registrado pelo usuário."""
    id: str
    name: str
    key_combination: str  # Ex: "Ctrl+Alt+W"
    action_type: str      # "open_tool", "run_command", "open_folder", "open_url"
    target: str           # Ex: "calc.salary_br", "explorer.exe", "https://..."
    enabled: bool = True


def parse_hotkey_string(hotkey_str: str) -> Optional[Tuple[int, int]]:
    """
    Converte uma string no formato 'Ctrl+Alt+K' em uma tupla (modifiers_bitmask, vk_code).
    """
    parts = [p.strip().upper() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return None

    mods = 0
    key_part = None

    for p in parts:
        if p in ["CTRL", "CONTROL"]:
            mods |= MOD_CONTROL
        elif p == "ALT":
            mods |= MOD_ALT
        elif p == "SHIFT":
            mods |= MOD_SHIFT
        elif p in ["WIN", "WINDOWS", "SUPER"]:
            mods |= MOD_WIN
        else:
            key_part = p

    if not key_part or key_part not in VK_MAP:
        return None

    return mods, VK_MAP[key_part]


def validate_hotkey_syntax(hotkey_str: str) -> bool:
    """Verifica se a string de atalho é válida e compreensível."""
    return parse_hotkey_string(hotkey_str) is not None


def save_hotkeys_json(hotkeys: List[GlobalHotkey], filepath: str) -> None:
    """Salva a lista de atalhos em arquivo JSON."""
    raw = [asdict(h) for h in hotkeys]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_hotkeys_json(filepath: str) -> List[GlobalHotkey]:
    """Carrega atalhos a partir de arquivo JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [
                GlobalHotkey(
                    id=d.get("id", ""),
                    name=d.get("name", "Atalho"),
                    key_combination=d.get("key_combination", ""),
                    action_type=d.get("action_type", "open_tool"),
                    target=d.get("target", ""),
                    enabled=d.get("enabled", True)
                )
                for d in raw if isinstance(d, dict)
            ]
    except Exception:
        return []
