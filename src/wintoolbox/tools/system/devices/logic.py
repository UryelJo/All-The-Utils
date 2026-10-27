"""
Lógica pura para diagnóstico de dispositivos PnP e histórico de periféricos USB.

Identifica dispositivos com códigos de erro do Windows (Código 10, 43, 28)
e consulta histórico de unidades de armazenamento USB no Registro/CIM.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import json
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.devices.logic")

# Mapeamento oficial dos códigos de erro do ConfigManager do Windows
CONFIG_MANAGER_ERRORS: Dict[int, str] = {
    1: "O dispositivo não está configurado corretamente (Código 1)",
    3: "O driver deste dispositivo pode estar corrompido (Código 3)",
    10: "O dispositivo não pode ser iniciado (Código 10)",
    12: "O dispositivo não encontrou recursos livres suficientes (Código 12)",
    14: "Este dispositivo não pode funcionar até que o computador seja reiniciado (Código 14)",
    18: "Reinstale os drivers para este dispositivo (Código 18)",
    22: "Este dispositivo está desabilitado (Código 22)",
    28: "Os drivers para este dispositivo não estão instalados (Código 28)",
    29: "Este dispositivo está desabilitado pelo firmware (Código 29)",
    31: "O Windows não pode carregar os drivers necessários (Código 31)",
    43: "O Windows interrompeu este dispositivo por problemas relatados (Código 43)",
    45: "O dispositivo de hardware não está conectado (Código 45)",
}


@dataclass
class PnpDevice:
    name: str
    device_id: str
    status: str
    error_code: int
    class_name: str
    manufacturer: str

    @property
    def has_error(self) -> bool:
        return self.error_code != 0 or self.status.upper() != "OK"

    @property
    def error_description(self) -> str:
        if self.error_code in CONFIG_MANAGER_ERRORS:
            return CONFIG_MANAGER_ERRORS[self.error_code]
        if self.error_code != 0:
            return f"Erro de hardware reportado (Código {self.error_code})"
        if self.status.upper() != "OK":
            return f"Status divergente: {self.status}"
        return "Funcionando normalmente"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["error_description"] = self.error_description
        return d


def parse_pnp_devices_json(json_str: str) -> List[PnpDevice]:
    """
    Analisa a saída JSON de Get-CimInstance Win32_PnPEntity.
    """
    if not json_str.strip():
        return []

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            data = [data]
    except Exception as e:
        _log.warning(f"Erro ao analisar JSON de dispositivos PnP: {e}")
        return []

    devices: List[PnpDevice] = []
    for item in data:
        name = str(item.get("Name") or item.get("Caption") or "Dispositivo Desconhecido").strip()
        dev_id = str(item.get("DeviceID") or "N/A").strip()
        status = str(item.get("Status") or "OK").strip()
        err_code = int(item.get("ConfigManagerErrorCode") or 0)
        pnp_class = str(item.get("PNPClass") or "Outros").strip()
        manuf = str(item.get("Manufacturer") or "Desconhecido").strip()

        devices.append(PnpDevice(
            name=name,
            device_id=dev_id,
            status=status,
            error_code=err_code,
            class_name=pnp_class,
            manufacturer=manuf
        ))

    return devices


def parse_usb_history_json(json_str: str) -> List[Dict[str, Any]]:
    """
    Analisa os dados de histórico de conexões USB do Registro.
    """
    if not json_str.strip():
        return []

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception as e:
        _log.warning(f"Erro ao analisar JSON de histórico USB: {e}")
        return []


def query_pnp_devices(errors_only: bool = False) -> List[PnpDevice]:
    """
    Consulta dispositivos PnP no Windows via CIM.
    """
    where_clause = "Where-Object { $_.ConfigManagerErrorCode -ne 0 -or $_.Status -ne 'OK' } | " if errors_only else ""
    ps_cmd = (
        f"Get-CimInstance Win32_PnPEntity | "
        f"{where_clause}"
        f"Select-Object Name, DeviceID, Status, ConfigManagerErrorCode, PNPClass, Manufacturer | "
        f"ConvertTo-Json -Depth 2 -Compress"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=25,
            check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return parse_pnp_devices_json(proc.stdout)
    except Exception as e:
        _log.warning(f"Falha ao consultar dispositivos PnP: {e}")

    return []


def query_usb_storage_history() -> List[Dict[str, Any]]:
    """
    Consulta o histórico de dispositivos de armazenamento USB conectados a partir do Registro.
    """
    ps_cmd = """
    $ErrorActionPreference = 'SilentlyContinue'
    $usb_keys = Get-ChildItem -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR'
    $results = @()
    foreach ($k in $usb_keys) {
        $dev_name = $k.PSChildName
        $sub = Get-ChildItem -Path $k.PSPath
        foreach ($s in $sub) {
            $serial = $s.PSChildName
            $friendly = (Get-ItemProperty -Path $s.PSPath -Name FriendlyName).FriendlyName
            if (-not $friendly) { $friendly = $dev_name }
            $results += [PSCustomObject]@{
                FriendlyName = $friendly
                DeviceName   = $dev_name
                SerialNumber = $serial
            }
        }
    }
    $results | ConvertTo-Json -Depth 2 -Compress
    """

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return parse_usb_history_json(proc.stdout)
    except Exception as e:
        _log.warning(f"Falha ao consultar histórico USB: {e}")

    return []
