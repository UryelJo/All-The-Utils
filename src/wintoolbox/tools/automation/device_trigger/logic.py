"""
Lógica pura para detecção de dispositivos removíveis (pendrives, HDs externos, cartões SD)
e automação acionada por eventos de hardware no Windows.
Desacoplada de frameworks de interface gráfica.
"""
import ctypes
from dataclasses import asdict, dataclass
import json
import os
import string
from typing import Any, Dict, List, Optional


DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6


@dataclass
class DeviceRule:
    """Regra de automação acionada pela conexão de um dispositivo."""
    id: str
    name: str
    volume_label_filter: str   # Ex: "PENDRIVE_FOTOS" ou "" para qualquer um
    action_type: str           # "open_explorer", "copy_to_folder", "run_script", "notify"
    target_path: str           # Destino ou comando
    enabled: bool = True


def get_drive_volume_label(drive_letter: str) -> str:
    """Obtém o rótulo de volume (nome) da unidade informada no Windows."""
    root_path = f"{drive_letter.rstrip(':\\')}:\\"
    volume_name_buf = ctypes.create_unicode_buffer(260)
    fs_name_buf = ctypes.create_unicode_buffer(260)
    serial_number = ctypes.c_ulong()
    max_component_length = ctypes.c_ulong()
    file_system_flags = ctypes.c_ulong()

    res = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root_path),
        volume_name_buf,
        ctypes.sizeof(volume_name_buf),
        ctypes.byref(serial_number),
        ctypes.byref(max_component_length),
        ctypes.byref(file_system_flags),
        fs_name_buf,
        ctypes.sizeof(fs_name_buf)
    )
    if res:
        return volume_name_buf.value
    return ""


def get_connected_removable_drives() -> List[Dict[str, str]]:
    """
    Lista todas as unidades lógicas removíveis atualmente conectadas ao sistema Windows.
    """
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    drives = []

    for letter in string.ascii_uppercase:
        if bitmask & 1:
            root = f"{letter}:\\"
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
            if drive_type == DRIVE_REMOVABLE:
                label = get_drive_volume_label(letter)
                drives.append({
                    "drive_letter": f"{letter}:",
                    "volume_label": label or "Disco Removível",
                    "root_path": root
                })
        bitmask >>= 1

    return drives


def match_drive_with_rule(rule: DeviceRule, volume_label: str) -> bool:
    """Verifica se a unidade conectada satisfaz o filtro da regra."""
    if not rule.enabled:
        return False
    filter_val = rule.volume_label_filter.strip().lower()
    if not filter_val or filter_val == "*":
        return True
    return filter_val in volume_label.lower()


def save_device_rules_json(rules: List[DeviceRule], filepath: str) -> None:
    """Salva a lista de regras de dispositivo em arquivo JSON."""
    raw = [asdict(r) for r in rules]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_device_rules_json(filepath: str) -> List[DeviceRule]:
    """Carrega regras de dispositivo a partir de arquivo JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [
                DeviceRule(
                    id=d.get("id", ""),
                    name=d.get("name", "Regra de Dispositivo"),
                    volume_label_filter=d.get("volume_label_filter", ""),
                    action_type=d.get("action_type", "open_explorer"),
                    target_path=d.get("target_path", ""),
                    enabled=d.get("enabled", True)
                )
                for d in raw if isinstance(d, dict)
            ]
    except Exception:
        return []
