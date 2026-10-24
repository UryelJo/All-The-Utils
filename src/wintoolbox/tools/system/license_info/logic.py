"""
Lógica pura de leitura de Chave do Produto (OEM/BIOS) e Status de Ativação do Windows.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import platform
import subprocess
from typing import Any, Dict, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.license_info")


def get_oem_bios_product_key() -> Optional[str]:
    """
    Recupera a chave de produto OEM gravada na placa-mãe (BIOS/UEFI MSDM).
    Disponível em computadores e notebooks de fabricantes (Dell, Lenovo, HP, Asus, etc.).
    """
    ps_cmd = "(Get-CimInstance -ClassName SoftwareLicensingService).OA3xOriginalProductKey"
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=15
        )
        key = proc.stdout.strip()
        if key and len(key) >= 20 and "-" in key:
            return key
    except Exception as exc:
        _log.warning("Falha ao consultar chave OEM da BIOS: %s", exc)

    return None


def get_windows_activation_status() -> Dict[str, Any]:
    """
    Consulta a edição atual do Windows e o status de licenciamento/ativação.
    """
    edition = platform.platform()
    res = {
        "edition": edition,
        "is_activated": False,
        "status_description": "Desconhecido",
        "partial_product_key": "",
        "license_channel": "Varejo (Retail) / OEM / Digital"
    }

    # Consulta status via cscript slmgr.vbs
    ps_cmd = "cscript //nologo C:\\Windows\\System32\\slmgr.vbs /dli"
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=15
        )
        output = proc.stdout.strip()

        for line in output.splitlines():
            line_str = line.strip()
            if "Nome:" in line_str or "Name:" in line_str:
                res["edition"] = line_str.split(":", 1)[1].strip()
            elif "Status da Licen" in line_str or "License Status:" in line_str:
                status_raw = line_str.split(":", 1)[1].strip()
                res["status_description"] = status_raw
                if "Licenciado" in status_raw or "Licensed" in status_raw:
                    res["is_activated"] = True
            elif "Chave do Produto Parcial:" in line_str or "Partial Product Key:" in line_str:
                res["partial_product_key"] = line_str.split(":", 1)[1].strip()
            elif "Descri" in line_str or "Description:" in line_str:
                res["license_channel"] = line_str.split(":", 1)[1].strip()

    except Exception as exc:
        _log.warning("Falha ao consultar slmgr: %s", exc)

    return res
