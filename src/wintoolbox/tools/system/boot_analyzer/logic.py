"""
Lógica pura para análise de desempenho de inicialização do Windows (Boot Performance).

Lê os eventos do canal oficial 'Microsoft-Windows-Diagnostics-Performance/Operational'
(Event ID 100) para calcular o tempo total de boot, tempo até a tela de login
e tempo pós-login gasto inicializando serviços e programas em segundo plano.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.boot_analyzer.logic")


@dataclass
class BootEventRecord:
    timestamp: str
    total_boot_sec: float
    main_path_sec: float
    post_boot_sec: float
    status_label: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_boot_time(seconds: float) -> str:
    """Classifica a velocidade de boot baseada em diretrizes de experiência do Windows."""
    if seconds <= 20.0:
        return "Excelente"
    elif seconds <= 35.0:
        return "Bom"
    elif seconds <= 60.0:
        return "Moderado"
    else:
        return "Lento (Requer Otimização)"


def parse_boot_xml_event(xml_text: str, created_time_str: str = "") -> Optional[BootEventRecord]:
    """
    Analisa o payload XML do Event ID 100 do Diagnostics-Performance.
    """
    if not xml_text.strip():
        return None

    try:
        # Remove namespaces para parsing direto e robusto
        clean_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_text)
        root = ET.fromstring(clean_xml)

        data_elements = root.findall(".//EventData/Data")
        data_map: Dict[str, str] = {}
        for elem in data_elements:
            name = elem.get("Name")
            if name and elem.text:
                data_map[name] = elem.text.strip()

        # Extrai tempos em milissegundos
        boot_ms = float(data_map.get("BootTime") or 0)
        main_ms = float(data_map.get("MainPathBootTime") or 0)
        post_ms = float(data_map.get("BootPostBootTime") or 0)

        if boot_ms <= 0:
            boot_ms = main_ms + post_ms

        boot_sec = round(boot_ms / 1000.0, 1)
        main_sec = round(main_ms / 1000.0, 1)
        post_sec = round(post_ms / 1000.0, 1)

        # Extrai timestamp do TimeCreated caso não tenha sido fornecido
        ts = created_time_str
        if not ts:
            time_created = root.find(".//System/TimeCreated")
            if time_created is not None:
                ts = time_created.get("SystemTime") or ""
                if "T" in ts:
                    parts = ts.split("T")
                    date_p = parts[0]
                    time_p = parts[1].split(".")[0]
                    ts = f"{date_p} {time_p}"

        return BootEventRecord(
            timestamp=ts or "Data Desconhecida",
            total_boot_sec=boot_sec,
            main_path_sec=main_sec,
            post_boot_sec=post_sec,
            status_label=classify_boot_time(boot_sec)
        )
    except Exception as e:
        _log.warning(f"Erro ao analisar XML de evento de boot: {e}")
        return None


def calculate_boot_summary(records: List[BootEventRecord]) -> Dict[str, Any]:
    """Calcula médias e métricas consolidadas dos registros de inicialização."""
    if not records:
        return {
            "count": 0,
            "avg_total_sec": 0.0,
            "avg_main_sec": 0.0,
            "avg_post_sec": 0.0,
            "fastest_sec": 0.0,
            "slowest_sec": 0.0,
        }

    totals = [r.total_boot_sec for r in records]
    mains = [r.main_path_sec for r in records]
    posts = [r.post_boot_sec for r in records]

    return {
        "count": len(records),
        "avg_total_sec": round(sum(totals) / len(totals), 1),
        "avg_main_sec": round(sum(mains) / len(mains), 1),
        "avg_post_sec": round(sum(posts) / len(posts), 1),
        "fastest_sec": min(totals),
        "slowest_sec": max(totals),
    }


def query_boot_performance_events(max_events: int = 15) -> List[BootEventRecord]:
    """
    Executa consulta PowerShell ao log Diagnostics-Performance no Windows.
    """
    ps_cmd = (
        f"Get-WinEvent -FilterHashtable @{{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=100}} "
        f"-MaxEvents {max_events} -ErrorAction SilentlyContinue | "
        f"Select-Object @{{Name='Time'; Expression={{$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}}}}, @{{Name='Xml'; Expression={{$_.ToXml()}}}} | "
        f"ConvertTo-Json -Depth 2 -Compress"
    )

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            raw_data = json.loads(res.stdout.strip())
            items = raw_data if isinstance(raw_data, list) else [raw_data]

            records: List[BootEventRecord] = []
            for it in items:
                xml_content = it.get("Xml") or ""
                time_str = it.get("Time") or ""
                rec = parse_boot_xml_event(xml_content, created_time_str=time_str)
                if rec:
                    records.append(rec)

            return records
    except Exception as e:
        _log.warning(f"Não foi possível obter eventos de inicialização: {e}")

    return []
