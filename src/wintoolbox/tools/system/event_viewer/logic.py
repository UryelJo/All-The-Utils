"""
Lógica pura para consulta e filtragem de logs de eventos do Windows (System, Application).

Focado na identificação rápida de problemas, falhas de sistema, travamentos e avisos
recentes (últimas 24h ou 7 dias) via Get-WinEvent, com exportação para CSV.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.event_viewer.logic")

LEVEL_MAP: Dict[int, str] = {
    1: "Crítico",
    2: "Erro",
    3: "Aviso",
    4: "Informação",
    5: "Detalhado",
}


@dataclass
class EventLogRecord:
    time_created: str
    provider_name: str
    event_id: int
    level_display: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_winevent_json(json_str: str) -> List[EventLogRecord]:
    """
    Analisa a saída JSON de Get-WinEvent e normaliza os registros.
    """
    if not json_str.strip():
        return []

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            data = [data]
    except Exception as e:
        _log.warning(f"Erro ao analisar JSON de eventos do Windows: {e}")
        return []

    records: List[EventLogRecord] = []
    for item in data:
        t = str(item.get("Time") or item.get("TimeCreated") or "Data N/A").strip()
        prov = str(item.get("ProviderName") or "Sistema").strip()
        ev_id = int(item.get("Id") or item.get("EventId") or 0)

        # Mapeia nível numérico ou string
        raw_level = item.get("Level")
        if isinstance(raw_level, int):
            lvl = LEVEL_MAP.get(raw_level, "Informação")
        else:
            lvl_str = str(item.get("LevelDisplayName") or raw_level or "Informação").strip()
            lvl = lvl_str if lvl_str else "Informação"

        msg = str(item.get("Message") or "").strip().replace("\r\n", " ").replace("\n", " ")
        if len(msg) > 600:
            msg = msg[:600] + "..."

        records.append(EventLogRecord(
            time_created=t,
            provider_name=prov,
            event_id=ev_id,
            level_display=lvl,
            message=msg
        ))

    return records


def export_events_to_csv(records: List[EventLogRecord], csv_path: Path) -> Path:
    """
    Exporta a lista de eventos para arquivo CSV formatado em UTF-8 com BOM (compatível com Excel).
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Data e Hora", "Nível", "ID do Evento", "Fonte / Provedor", "Mensagem"])
        for r in records:
            writer.writerow([r.time_created, r.level_display, r.event_id, r.provider_name, r.message])

    return csv_path


def query_windows_event_log(
    log_name: str = "System",
    severity: str = "ErrorsAndWarnings",  # "ErrorsOnly", "ErrorsAndWarnings", "All"
    hours_back: int = 24,
    max_events: int = 150
) -> List[EventLogRecord]:
    """
    Executa consulta PowerShell Get-WinEvent com filtro de tempo e nível.
    """
    if severity == "ErrorsOnly":
        level_filter = "Level=1,2;"
    elif severity == "ErrorsAndWarnings":
        level_filter = "Level=1,2,3;"
    else:
        level_filter = ""

    ps_script = f"""
    $ErrorActionPreference = 'SilentlyContinue'
    $cutoff = (Get-Date).AddHours(-{hours_back})
    $filter = @{{
        LogName = '{log_name}'
        StartTime = $cutoff
        {level_filter}
    }}
    Get-WinEvent -FilterHashtable $filter -MaxEvents {max_events} |
        Select-Object @{{Name='Time'; Expression={{$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}}}},
                      ProviderName,
                      Id,
                      LevelDisplayName,
                      Level,
                      Message |
        ConvertTo-Json -Depth 2 -Compress
    """

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return parse_winevent_json(proc.stdout)
    except Exception as e:
        _log.warning(f"Erro ao consultar log de eventos do Windows: {e}")

    return []
