"""
Lógica pura para parsing, manipulação e geração de arquivos de calendário iCalendar (.ics - RFC 5545).
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    dtstart: str  # ISO: YYYY-MM-DDTHH:MM:SS ou YYYY-MM-DD
    dtend: str    # ISO: YYYY-MM-DDTHH:MM:SS ou YYYY-MM-DD
    description: str = ""
    location: str = ""
    all_day: bool = False


def _parse_ical_datetime(val: str) -> str:
    """Converte representação iCalendar (ex: 20261027T153000Z ou 20261027) para formato ISO."""
    clean = re.sub(r'^[A-Z0-9_-]+=', '', val.strip())  # Remove parâmetros como TZID
    clean = clean.replace("Z", "").replace("z", "")

    if "T" in clean:
        parts = clean.split("T")
        d_part = parts[0]
        t_part = parts[1]
        if len(d_part) >= 8 and len(t_part) >= 4:
            y, m, d = d_part[0:4], d_part[4:6], d_part[6:8]
            hh = t_part[0:2]
            mm = t_part[2:4]
            ss = t_part[4:6] if len(t_part) >= 6 else "00"
            return f"{y}-{m}-{d}T{hh}:{mm}:{ss}"
    elif len(clean) >= 8:
        y, m, d = clean[0:4], clean[4:6], clean[6:8]
        return f"{y}-{m}-{d}"

    return val


def _format_to_ical_datetime(dt_str: str) -> str:
    """Converte data/hora ISO para o formato iCalendar RFC 5545."""
    clean = dt_str.replace("-", "").replace(":", "")
    if "T" in clean:
        return f"{clean}Z"
    return clean


def parse_ics_content(content: str) -> List[CalendarEvent]:
    """Interpreta texto de arquivo iCalendar (.ics) e extrai a lista de eventos."""
    events: List[CalendarEvent] = []

    # Desdobra linhas quebradas (continuação com espaço ou tabulação na linha seguinte)
    unfolded = re.sub(r'\r?\n[ \t]', '', content)
    lines = unfolded.splitlines()

    in_event = False
    current_data: Dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line == "BEGIN:VEVENT":
            in_event = True
            current_data = {}
            continue

        if line == "END:VEVENT":
            in_event = False
            summary = current_data.get("SUMMARY", "Sem título")
            dtstart_raw = current_data.get("DTSTART", "")
            dtend_raw = current_data.get("DTEND", dtstart_raw)
            dtstart = _parse_ical_datetime(dtstart_raw)
            dtend = _parse_ical_datetime(dtend_raw)
            all_day = "T" not in dtstart

            events.append(
                CalendarEvent(
                    uid=current_data.get("UID", str(uuid.uuid4())),
                    summary=summary,
                    dtstart=dtstart,
                    dtend=dtend,
                    description=current_data.get("DESCRIPTION", ""),
                    location=current_data.get("LOCATION", ""),
                    all_day=all_day
                )
            )
            continue

        if in_event and ":" in line:
            key_part, val_part = line.split(":", 1)
            key = key_part.split(";")[0].upper()
            current_data[key] = val_part.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")

    return events


def generate_ics_content(events: List[CalendarEvent], cal_name: str = "WinToolbox Calendar") -> str:
    """Gera o arquivo de texto .ics formatado de acordo com RFC 5545."""
    now_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WinToolbox//Calendar Tool//PT",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{cal_name}",
    ]

    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev.uid}")
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"SUMMARY:{ev.summary}")
        lines.append(f"DTSTART:{_format_to_ical_datetime(ev.dtstart)}")
        lines.append(f"DTEND:{_format_to_ical_datetime(ev.dtend)}")
        if ev.description:
            desc_escaped = ev.description.replace("\n", "\\n").replace(",", "\\,")
            lines.append(f"DESCRIPTION:{desc_escaped}")
        if ev.location:
            lines.append(f"LOCATION:{ev.location}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def get_default_calendar_events() -> List[CalendarEvent]:
    """Retorna eventos de exemplo padrão."""
    today = date.today()
    dt_str1 = f"{today.isoformat()}T10:00:00"
    dt_str2 = f"{today.isoformat()}T11:30:00"
    return [
        CalendarEvent(
            uid=str(uuid.uuid4()),
            summary="Reunião de Alinhamento Semanal",
            dtstart=dt_str1,
            dtend=dt_str2,
            description="Revisão de sprints e entregas do projeto.",
            location="Sala Virtual / Teams"
        )
    ]


def save_events_to_ics(events: List[CalendarEvent], path: Path) -> None:
    """Salva a lista de eventos em arquivo .ics."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    ics_text = generate_ics_content(events)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics_text)


def load_events_from_ics(path: Path) -> List[CalendarEvent]:
    """Carrega eventos de um arquivo .ics do disco."""
    path = Path(path).resolve()
    if not path.is_file():
        return get_default_calendar_events()

    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            return parse_ics_content(content)
        except Exception:
            continue

    return get_default_calendar_events()
