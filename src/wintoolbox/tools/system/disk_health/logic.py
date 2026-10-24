"""
Lógica pura de análise de saúde, integridade SMART e desgaste de discos e SSDs.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.disk_health")


def format_bytes(size_bytes: int) -> str:
    """Converte bytes para representação legível (GB ou TB)."""
    if size_bytes <= 0:
        return "0 GB"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1024:
        return f"{gb / 1024:.2f} TB"
    return f"{gb:.1f} GB"


def get_disks_health_info() -> List[Dict[str, Any]]:
    """
    Consulta os discos físicos e contadores de confiabilidade de armazenamento
    do Windows via PowerShell (Get-PhysicalDisk e Get-StorageReliabilityCounter).
    """
    disks_dict: Dict[str, Dict[str, Any]] = {}

    # 1. Consulta discos físicos
    ps_cmd_disks = (
        "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType, "
        "Size, OperationalStatus, HealthStatus | ConvertTo-Json -Compress"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd_disks],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=20
        )
        stdout = proc.stdout.strip()
        if stdout:
            parsed = json.loads(stdout)
            # Pode ser um objeto único ou lista
            disk_list = [parsed] if isinstance(parsed, dict) else parsed
            for d in disk_list:
                dev_id = str(d.get("DeviceId", "")).strip()
                raw_size = int(d.get("Size") or 0)
                disks_dict[dev_id] = {
                    "device_id": dev_id,
                    "name": d.get("FriendlyName", "Disco Físico Desconhecido"),
                    "media_type": d.get("MediaType", "Não especificado"),
                    "bus_type": d.get("BusType", "SATA/NVMe"),
                    "size_bytes": raw_size,
                    "size_str": format_bytes(raw_size),
                    "health_status": d.get("HealthStatus", "Healthy"),
                    "operational_status": d.get("OperationalStatus", "OK"),
                    "temperature_c": None,
                    "wear_percent": None,
                    "read_errors": 0,
                    "write_errors": 0,
                    "power_on_hours": None
                }
    except Exception as exc:
        _log.warning("Falha ao consultar Get-PhysicalDisk: %s", exc)

    # 2. Consulta contadores de confiabilidade (SMART / StorageReliabilityCounter)
    ps_cmd_smart = (
        "Get-PhysicalDisk | Get-StorageReliabilityCounter | "
        "Select-Object DeviceId, Temperature, Wear, ReadErrorsTotal, WriteErrorsTotal, PowerOnHours | "
        "ConvertTo-Json -Compress"
    )

    try:
        proc_smart = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd_smart],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=20
        )
        stdout_smart = proc_smart.stdout.strip()
        if stdout_smart:
            parsed_smart = json.loads(stdout_smart)
            smart_list = [parsed_smart] if isinstance(parsed_smart, dict) else parsed_smart
            for s in smart_list:
                dev_id = str(s.get("DeviceId", "")).strip()
                if dev_id in disks_dict:
                    disks_dict[dev_id]["temperature_c"] = s.get("Temperature")
                    disks_dict[dev_id]["wear_percent"] = s.get("Wear")
                    disks_dict[dev_id]["read_errors"] = s.get("ReadErrorsTotal", 0)
                    disks_dict[dev_id]["write_errors"] = s.get("WriteErrorsTotal", 0)
                    disks_dict[dev_id]["power_on_hours"] = s.get("PowerOnHours")
    except Exception as exc:
        _log.warning("Falha ao consultar Get-StorageReliabilityCounter: %s", exc)

    # Se não obteve nada, faz fallback para WMI Win32_DiskDrive
    if not disks_dict:
        disks_dict = _get_wmi_disk_fallback()

    return list(disks_dict.values())


def _get_wmi_disk_fallback() -> Dict[str, Dict[str, Any]]:
    """Fallback simples caso os cmdlets de Storage estejam desabilitados."""
    res = {}
    try:
        import wmi
        c = wmi.WMI()
        for i, drive in enumerate(c.Win32_DiskDrive()):
            dev_id = str(i)
            size = int(drive.Size or 0)
            res[dev_id] = {
                "device_id": dev_id,
                "name": drive.Model or "Disco Local",
                "media_type": drive.MediaType or "Fixo",
                "bus_type": drive.InterfaceType or "SATA",
                "size_bytes": size,
                "size_str": format_bytes(size),
                "health_status": drive.Status or "OK",
                "operational_status": "OK",
                "temperature_c": None,
                "wear_percent": None,
                "read_errors": 0,
                "write_errors": 0,
                "power_on_hours": None
            }
    except Exception as exc:
        _log.warning("Fallback WMI falhou: %s", exc)
    return res
