"""
Lógica pura de leitura de Chave do Produto (OEM/BIOS), Status de Ativação e Gerenciamento slmgr
para Windows 10 e Windows 11.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import platform
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW

_log = get_logger("system.license_info")

# Chaves oficiais de configuração de cliente (KMS / Edições Windows 10 e Windows 11 da documentação Microsoft)
WINDOWS_10_11_EDITION_KEYS: List[Dict[str, str]] = [
    {"edition": "Windows 10 / 11 Pro", "key": "W269N-WFGWX-YVC9B-4J6C9-T83GX"},
    {"edition": "Windows 10 / 11 Home", "key": "TX9XD-98N7V-6WMQ6-BX7FG-H8Q99"},
    {"edition": "Windows 10 / 11 Home Single Language", "key": "7HNRX-D7KGG-3K4RQ-4WPJ4-YTDFH"},
    {"edition": "Windows 10 / 11 Pro for Workstations", "key": "NRG8B-VKK3Q-CXVCJ-9G2XF-6Q84J"},
    {"edition": "Windows 10 / 11 Pro Education", "key": "6TP4R-GNPTD-KYYHQ-7B7DP-J447Y"},
    {"edition": "Windows 10 / 11 Education", "key": "NW6C2-QMPVW-D7KKK-3GKT6-VCFB2"},
    {"edition": "Windows 10 / 11 Enterprise", "key": "NPPR9-FWDCX-D2C8J-H872K-2YT43"},
    {"edition": "Windows 10 / 11 Enterprise LTSC", "key": "M7XTQ-FN8P6-TTKYV-9D4CC-J462D"},
    {"edition": "Windows 10 / 11 Pro N", "key": "MH37W-N47XK-V7XM9-C7227-GCQG9"},
]

PRODUCT_KEY_REGEX = re.compile(r"^[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}$", re.IGNORECASE)


def validate_product_key_format(key_str: str) -> bool:
    """Valida se a chave segue o padrão de 25 caracteres (XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)."""
    return bool(PRODUCT_KEY_REGEX.match((key_str or "").strip()))


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
            creationflags=CREATE_NO_WINDOW,
            timeout=15,
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
        "license_channel": "Varejo (Retail) / OEM / Digital",
    }

    ps_cmd = "cscript //nologo C:\\Windows\\System32\\slmgr.vbs /dli"
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding=CONSOLE_ENCODING,
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=15,
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


def _run_slmgr(args: List[str], timeout: int = 30) -> Tuple[bool, str]:
    cmd = ["cscript.exe", "//nologo", r"C:\Windows\System32\slmgr.vbs", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=CONSOLE_ENCODING,
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode == 0 and not any(
            err_k in out.lower() for err_k in ("erro:", "error:", "0x", "acesso negado", "access denied")
        ):
            return True, out or "Operação concluída com sucesso."
        return False, out or f"Falha ao executar slmgr (código {proc.returncode})."
    except Exception as exc:
        return False, f"Erro ao executar slmgr: {exc}"


def install_product_key(product_key: str) -> Tuple[bool, str]:
    """Instala uma chave de produto para Windows 10 ou Windows 11 via 'slmgr.vbs /ipk'."""
    clean_key = (product_key or "").strip().upper()
    if not validate_product_key_format(clean_key):
        return False, "Formato de chave inválido. Use o padrão de 25 caracteres: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX."
    return _run_slmgr(["/ipk", clean_key])


def set_kms_server(kms_host: str) -> Tuple[bool, str]:
    """Configura o servidor KMS para ativação corporativa via 'slmgr.vbs /skms'."""
    host = (kms_host or "").strip()
    if not host:
        return False, "Informe o endereço do servidor KMS."
    return _run_slmgr(["/skms", host])


def activate_windows_online() -> Tuple[bool, str]:
    """Aciona a ativação online do Windows 10/11 via 'slmgr.vbs /ato'."""
    return _run_slmgr(["/ato"], timeout=45)


def check_activation_expiration() -> Tuple[bool, str]:
    """Consulta a data de expiração ou status permanente da ativação via 'slmgr.vbs /xpr'."""
    return _run_slmgr(["/xpr"], timeout=20)
