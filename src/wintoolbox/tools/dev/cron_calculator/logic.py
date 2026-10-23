"""
Lógica pura de análise, tradução em linguagem natural (pt-BR) e cálculo de execuções de expressões Cron.
Totalmente desacoplada de interface gráfica e bibliotecas externas.
"""
from datetime import datetime, timedelta
import calendar
from typing import Dict, List, Optional, Set, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.cron_calculator")

MONTH_NAMES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

DOW_NAMES = {
    0: "Domingo", 1: "Segunda-feira", 2: "Terça-feira",
    3: "Quarta-feira", 4: "Quinta-feira", 5: "Sexta-feira",
    6: "Sábado", 7: "Domingo"
}

MONTH_ALIASES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

DOW_ALIASES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6
}

PRESETS = [
    ("A cada minuto", "* * * * *"),
    ("A cada 5 minutos", "*/5 * * * *"),
    ("A cada 15 minutos", "*/15 * * * *"),
    ("A cada 30 minutos", "*/30 * * * *"),
    ("No início de cada hora", "0 * * * *"),
    ("Diariamente à meia-noite", "0 0 * * *"),
    ("Diariamente às 08:00", "0 8 * * *"),
    ("Dias úteis às 09:00 (Seg a Sex)", "0 9 * * 1-5"),
    ("Semanalmente no Domingo à meia-noite", "0 0 * * 0"),
    ("Primeiro dia do mês à meia-noite", "0 0 1 * *"),
    ("A cada hora em horário comercial (9h-18h seg a sex)", "0 9-18 * * 1-5"),
]


def _parse_field(
    field_str: str,
    min_val: int,
    max_val: int,
    aliases: Optional[Dict[str, int]] = None
) -> Set[int]:
    """Interpreta um campo individual cron (*, */n, a-b, a,b,c) e retorna o conjunto de inteiros válidos."""
    s = field_str.strip().upper()
    if aliases:
        for name, num in aliases.items():
            s = s.replace(name, str(num))

    results: Set[int] = set()

    for part in s.split(","):
        part = part.strip()
        if not part:
            continue

        if part == "*":
            results.update(range(min_val, max_val + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"Passo inválido no cron: {step}")
            results.update(range(min_val, max_val + 1, step))
        elif "/" in part:
            subparts = part.split("/")
            range_part = subparts[0]
            step = int(subparts[1])
            if step <= 0:
                raise ValueError(f"Passo inválido no cron: {step}")
            if range_part == "*":
                start, end = min_val, max_val
            elif "-" in range_part:
                start_s, end_s = range_part.split("-")
                start, end = int(start_s), int(end_s)
            else:
                start = int(range_part)
                end = max_val
            results.update(range(start, end + 1, step))
        elif "-" in part:
            start_s, end_s = part.split("-")
            start, end = int(start_s), int(end_s)
            if start > end or start < min_val or end > max_val:
                raise ValueError(f"Intervalo inválido {start}-{end}")
            results.update(range(start, end + 1))
        else:
            val = int(part)
            if val < min_val or val > max_val:
                raise ValueError(f"Valor fora dos limites [{min_val}, {max_val}]: {val}")
            results.add(val)

    return results


def parse_cron(cron_expr: str) -> Tuple[Set[int], Set[int], Set[int], Set[int], Set[int], Optional[Set[int]]]:
    """
    Interpreta expressão de 5 campos (min, hora, dia_mes, mes, dia_sem)
    ou 6 campos (seg, min, hora, dia_mes, mes, dia_sem).
    """
    parts = cron_expr.strip().split()
    if len(parts) == 5:
        has_sec = False
        sec_set = None
        min_str, hr_str, dom_str, mon_str, dow_str = parts
    elif len(parts) == 6:
        has_sec = True
        sec_str, min_str, hr_str, dom_str, mon_str, dow_str = parts
        sec_set = _parse_field(sec_str, 0, 59)
    else:
        raise ValueError("A expressão cron deve conter 5 campos (padrão) ou 6 campos (com segundos).")

    min_set = _parse_field(min_str, 0, 59)
    hr_set = _parse_field(hr_str, 0, 23)
    dom_set = _parse_field(dom_str, 1, 31)
    mon_set = _parse_field(mon_str, 1, 12, MONTH_ALIASES)
    dow_set = _parse_field(dow_str, 0, 7, DOW_ALIASES)

    # Normalizar domingo: 7 vira 0
    if 7 in dow_set:
        dow_set.remove(7)
        dow_set.add(0)

    return min_set, hr_set, dom_set, mon_set, dow_set, sec_set


def explain_cron(cron_expr: str) -> str:
    """Traduz semântica da expressão cron para português do Brasil claro e natural."""
    try:
        parts = cron_expr.strip().split()
        if len(parts) not in (5, 6):
            return "Expressão inválida. Esperado 5 ou 6 campos separados por espaço."

        if len(parts) == 6:
            sec_s, min_s, hr_s, dom_s, mon_s, dow_s = parts
        else:
            sec_s = None
            min_s, hr_s, dom_s, mon_s, dow_s = parts

        # Casos comuns pré-definidos rápidos
        for label, expr in PRESETS:
            if cron_expr.strip() == expr:
                return f"{label} ({expr})"

        desc_parts: List[str] = []

        # Segundos
        if sec_s is not None:
            if sec_s == "*":
                desc_parts.append("A cada segundo")
            elif sec_s.startswith("*/"):
                desc_parts.append(f"A cada {sec_s[2:]} segundos")
            else:
                desc_parts.append(f"No segundo {sec_s}")

        # Minutos e Horas
        if min_s == "*" and hr_s == "*":
            if not desc_parts:
                desc_parts.append("A cada minuto")
        elif min_s.startswith("*/") and hr_s == "*":
            desc_parts.append(f"A cada {min_s[2:]} minutos")
        elif min_s == "0" and hr_s == "*":
            desc_parts.append("No início de cada hora")
        elif min_s == "0" and hr_s.startswith("*/"):
            desc_parts.append(f"A cada {hr_s[2:]} horas")
        elif hr_s != "*" and min_s != "*":
            desc_parts.append(f"Às {hr_s.zfill(2)}:{min_s.zfill(2)}")
        elif hr_s != "*":
            desc_parts.append(f"Durante a hora {hr_s}, no minuto {min_s}")
        else:
            desc_parts.append(f"No minuto {min_s} de cada hora")

        # Dia do mês
        if dom_s != "*":
            if dom_s.startswith("*/"):
                desc_parts.append(f"a cada {dom_s[2:]} dias")
            else:
                desc_parts.append(f"no dia {dom_s} do mês")

        # Mês
        if mon_s != "*":
            if mon_s.isdigit() and int(mon_s) in MONTH_NAMES:
                desc_parts.append(f"em {MONTH_NAMES[int(mon_s)]}")
            else:
                desc_parts.append(f"no mês {mon_s}")

        # Dia da semana
        if dow_s != "*":
            if dow_s == "1-5":
                desc_parts.append("de segunda a sexta-feira")
            elif dow_s in ("0,6", "6,0"):
                desc_parts.append("nos fins de semana (sábado e domingo)")
            elif dow_s.isdigit() and int(dow_s) in DOW_NAMES:
                desc_parts.append(f"em cada {DOW_NAMES[int(dow_s)]}")
            else:
                desc_parts.append(f"no dia da semana {dow_s}")

        return ", ".join(desc_parts)

    except Exception as exc:
        return f"Erro ao analisar expressão: {exc}"


def get_next_cron_occurrences(
    cron_expr: str,
    count: int = 10,
    start_time: Optional[datetime] = None
) -> List[datetime]:
    """Calcula as próximas N ocorrências de uma expressão cron a partir de start_time."""
    if start_time is None:
        start_time = datetime.now()

    min_set, hr_set, dom_set, mon_set, dow_set, sec_set = parse_cron(cron_expr)

    # Avança para o próximo minuto/segundo exato
    if sec_set is not None:
        current = start_time.replace(microsecond=0) + timedelta(seconds=1)
        step = timedelta(seconds=1)
    else:
        current = start_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        step = timedelta(minutes=1)

    occurrences: List[datetime] = []
    # Limite de segurança de iterações para evitar loop infinito
    max_steps = 500000
    steps = 0

    while len(occurrences) < count and steps < max_steps:
        steps += 1

        # Checar mês
        if current.month not in mon_set:
            # Avança para início do próximo mês
            year = current.year + (1 if current.month == 12 else 0)
            month = 1 if current.month == 12 else current.month + 1
            current = datetime(year, month, 1, 0, 0, 0)
            continue

        # Checar dia do mês e dia da semana
        # Python weekday: Seg=0, Dom=6. Cron: Dom=0, Seg=1, ..., Sab=6
        cron_dow = (current.weekday() + 1) % 7
        if (current.day not in dom_set) or (cron_dow not in dow_set):
            # Avança para início do próximo dia
            current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            continue

        # Checar hora
        if current.hour not in hr_set:
            current = (current + timedelta(hours=1)).replace(minute=0, second=0)
            continue

        # Checar minuto
        if current.minute not in min_set:
            current = (current + timedelta(minutes=1)).replace(second=0)
            continue

        # Checar segundo se aplicável
        if sec_set is not None and current.second not in sec_set:
            current += timedelta(seconds=1)
            continue

        occurrences.append(current)
        current += step

    return occurrences
