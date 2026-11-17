"""
Lógica pura de análise de saúde, integridade SMART, diagnóstico detalhado e desgaste de discos e SSDs.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.disk_health")

SMART_PARAMETER_TOOLTIPS: Dict[str, str] = {
    "media_type": (
        "Tipo físico da unidade de armazenamento:\n"
        "• SSD (Solid State Drive): Memória flash NAND sem partes móveis, alta velocidade.\n"
        "• HDD (Hard Disk Drive): Disco magnético mecânico tradicional.\n"
        "• Unspecified / SCM: Unidade virtual, NVMe específico ou memória de classe de armazenamento."
    ),
    "bus_type": (
        "Interface de comunicação com a placa-mãe:\n"
        "• NVMe: Barramento PCIe de altíssima velocidade e baixa latência.\n"
        "• SATA: Barramento tradicional (até 600 MB/s).\n"
        "• USB / RAID / SAS: Conexão externa ou controladora dedicada."
    ),
    "temperature_c": (
        "Temperatura interna atual reportada pelo sensor SMART da unidade:\n"
        "• Ideal: entre 25 °C e 50 °C.\n"
        "• Aceitável em carga intensa (NVMe): até 65 °C.\n"
        "• Crítico (> 70 °C): Pode causar thermal throttling (redução de velocidade) e desgaste prematuro."
    ),
    "power_on_hours": (
        "Total acumulado de horas em que o disco esteve energizado desde a fabricação (SMART ID 09 - Power-On Hours).\n"
        "Útil para estimar o tempo de uso real da unidade."
    ),
    "errors": (
        "Contadores acumulados de erros físicos de leitura e escrita não recuperados imediatamente pela controladora:\n"
        "• Ideal: 0 / 0.\n"
        "• Valores crescentes indicam setores defeituosos (Bad Blocks) ou falha de mídia ou cabo."
    ),
    "operational_status": (
        "Estado operacional imediato da unidade perante o subsistema de armazenamento do Windows:\n"
        "• OK: Funcionando perfeitamente sem pendências de I/O.\n"
        "• Degraded / Predictive Failure: Falha iminente detectada."
    ),
    "wear_percent": (
        "Nível de desgaste das células de memória flash NAND do SSD (Percentage Used / Wear Leveling):\n"
        "• 0% a 10% de desgaste (90-100% de vida útil): Estado de disco novo/excelente.\n"
        "• Acima de 80% de desgaste (< 20% de vida útil): Recomenda-se planejar backup preventivo."
    ),
}


def format_bytes(size_bytes: int) -> str:
    """Converte bytes para representação legível (GB ou TB)."""
    if size_bytes <= 0:
        return "0 GB"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1024:
        return f"{gb / 1024:.2f} TB"
    return f"{gb:.1f} GB"


def build_disk_health_diagnosis(disk: Dict[str, Any]) -> str:
    """
    Constrói uma justificativa técnica detalhada explicando por que o disco
    foi classificado como Saudável, Em Atenção ou Crítico.
    """
    reasons: List[str] = []
    health = str(disk.get("health_status", "Healthy")).upper()
    op_status = str(disk.get("operational_status", "OK"))
    temp = disk.get("temperature_c")
    wear = disk.get("wear_percent")
    r_err = int(disk.get("read_errors") or 0)
    w_err = int(disk.get("write_errors") or 0)

    if "HEALTHY" in health or "OK" in health:
        reasons.append("Autodiagnóstico SMART da controladora reporta integridade normal (Healthy)")
    else:
        reasons.append(f"Controladora reportou alerta de integridade ({disk.get('health_status')})")

    if op_status.upper() == "OK":
        reasons.append("status operacional ativo sem falhas de comunicação")
    else:
        reasons.append(f"estado operacional requer verificação ({op_status})")

    if temp is not None:
        if temp <= 55:
            reasons.append(f"temperatura segura ({temp} °C, dentro da faixa ideal <= 55 °C)")
        elif temp <= 68:
            reasons.append(f"temperatura moderada/elevada ({temp} °C, atenção à ventilação)")
        else:
            reasons.append(f"temperatura crítica ({temp} °C, acima do limite seguro de 70 °C)")

    if wear is not None:
        rem = max(0, 100 - int(wear))
        if rem >= 80:
            reasons.append(f"células NAND preservadas ({rem}% de vida útil restante)")
        elif rem >= 30:
            reasons.append(f"desgaste moderado de células NAND ({rem}% de vida útil restante)")
        else:
            reasons.append(f"desgaste avançado de SSD ({rem}% de vida útil restante — faça backup)")

    if r_err == 0 and w_err == 0:
        reasons.append("zero erros físicos de leitura ou escrita registrados")
    else:
        reasons.append(f"foram contabilizados {r_err} erro(s) de leitura e {w_err} de escrita")

    return "Diagnóstico: " + "; ".join(reasons) + "."


def get_disks_health_info() -> List[Dict[str, Any]]:
    """
    Consulta os discos físicos e contadores de confiabilidade de armazenamento
    do Windows via PowerShell (Get-PhysicalDisk e Get-StorageReliabilityCounter).
    """
    disks_dict: Dict[str, Dict[str, Any]] = {}

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
            timeout=20,
        )
        stdout = proc.stdout.strip()
        if stdout:
            parsed = json.loads(stdout)
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
                    "power_on_hours": None,
                }
    except Exception as exc:
        _log.warning("Falha ao consultar Get-PhysicalDisk: %s", exc)

    ps_cmd_smart = (
        "Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | "
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
            timeout=20,
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
                    disks_dict[dev_id]["read_errors"] = s.get("ReadErrorsTotal") or 0
                    disks_dict[dev_id]["write_errors"] = s.get("WriteErrorsTotal") or 0
                    disks_dict[dev_id]["power_on_hours"] = s.get("PowerOnHours")
    except Exception as exc:
        _log.warning("Falha ao consultar Get-StorageReliabilityCounter: %s", exc)

    if not disks_dict:
        disks_dict = _get_wmi_disk_fallback()

    result = list(disks_dict.values())
    for item in result:
        item["diagnosis_summary"] = build_disk_health_diagnosis(item)
    return result


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
                "power_on_hours": None,
            }
    except Exception as exc:
        _log.warning("Fallback WMI falhou: %s", exc)
    return res
