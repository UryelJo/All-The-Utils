"""
Lógica pura de relógio mundial e conversão de fusos horários (Timezones).
Utiliza a biblioteca padrão zoneinfo sem dependências externas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import zoneinfo

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("calc.world_clock")

POPULAR_TIMEZONES = [
    ("Brasília / São Paulo", "America/Sao_Paulo", "Brasil (UTC-3)"),
    ("UTC / GMT (Meridiano)", "UTC", "Padrão Internacional"),
    ("Nova York (EST/EDT)", "America/New_York", "Estados Unidos (Leste)"),
    ("Los Angeles (PST/PDT)", "America/Los_Angeles", "Estados Unidos (Oeste)"),
    ("Londres (GMT/BST)", "Europe/London", "Reino Unido"),
    ("Paris / Berlim (CET)", "Europe/Paris", "Europa Central"),
    ("Moscou (MSK)", "Europe/Moscow", "Rússia"),
    ("Dubai (GST)", "Asia/Dubai", "Emirados Árabes"),
    ("Nova Déli (IST)", "Asia/Kolkata", "Índia"),
    ("Tóquio (JST)", "Asia/Tokyo", "Japão"),
    ("Pequim / Xangai (CST)", "Asia/Shanghai", "China"),
    ("Sydney (AEST/AEDT)", "Australia/Sydney", "Austrália"),
    ("Auckland (NZST/NZDT)", "Pacific/Auckland", "Nova Zelândia")
]


def get_available_timezones() -> List[str]:
    """Retorna lista ordenada de todos os identificadores IANA válidos."""
    return sorted(list(zoneinfo.available_timezones()))


def get_current_time_for_zone(tz_name: str) -> Dict[str, Any]:
    """Retorna a hora atual, offset e sigla para o fuso especificado."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    now = datetime.now(tz)
    offset = now.strftime("%z")
    formatted_offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"

    return {
        "tz_name": tz_name,
        "datetime": now.isoformat(),
        "time_str": now.strftime("%H:%M:%S"),
        "date_str": now.strftime("%d/%m/%Y"),
        "offset_str": formatted_offset,
        "tz_abbr": now.strftime("%Z")
    }


def get_all_world_clocks() -> List[Dict[str, Any]]:
    """Retorna os horários atuais de todas as cidades e fusos de referência."""
    results = []
    for city_name, tz_name, region in POPULAR_TIMEZONES:
        data = get_current_time_for_zone(tz_name)
        data["city"] = city_name
        data["region"] = region
        results.append(data)
    return results


def convert_time_between_zones(
    dt: datetime,
    source_tz_name: str,
    target_tz_name: str
) -> Dict[str, Any]:
    """Converte um horário de um fuso de origem para um fuso de destino."""
    try:
        src_tz = zoneinfo.ZoneInfo(source_tz_name)
        dst_tz = zoneinfo.ZoneInfo(target_tz_name)
    except Exception as exc:
        raise ValueError(f"Fuso horário inválido: {exc}")

    # Associa o fuso de origem se for ingênuo (naive)
    if dt.tzinfo is None:
        localized_dt = dt.replace(tzinfo=src_tz)
    else:
        localized_dt = dt.astimezone(src_tz)

    converted_dt = localized_dt.astimezone(dst_tz)

    offset_src = localized_dt.strftime("%z")
    offset_dst = converted_dt.strftime("%z")

    return {
        "source_dt": localized_dt.isoformat(),
        "source_str": localized_dt.strftime("%d/%m/%Y %H:%M:%S"),
        "source_offset": f"UTC{offset_src[:3]}:{offset_src[3:]}",
        "target_dt": converted_dt.isoformat(),
        "target_str": converted_dt.strftime("%d/%m/%Y %H:%M:%S"),
        "target_offset": f"UTC{offset_dst[:3]}:{offset_dst[3:]}",
        "target_abbr": converted_dt.strftime("%Z")
    }
