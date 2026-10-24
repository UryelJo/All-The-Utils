"""
Lógica pura de cálculos temporais, diferença entre datas e contagem de dias úteis.
Isolada de bibliotecas visuais ou dependências externas.
"""
import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("calc.date_calculator")

# Feriados nacionais fixos brasileiros (mês, dia, nome)
FIXED_BRAZILIAN_HOLIDAYS = [
    (1, 1, "Confraternização Universal"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do Trabalhador"),
    (9, 7, "Independência do Brasil"),
    (10, 12, "Nossa Senhora Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (11, 20, "Dia Nacional de Zumbi e da Consciência Negra"),
    (12, 25, "Natal"),
]


def calculate_easter(year: int) -> date:
    """Calcula a Páscoa pelo algoritmo de Butcher (Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_brazilian_holidays(year: int) -> Dict[date, str]:
    """Retorna o dicionário de feriados nacionais para o ano fornecido."""
    holidays = {}
    for m, d, name in FIXED_BRAZILIAN_HOLIDAYS:
        holidays[date(year, m, d)] = name

    # Feriados móveis derivados da Páscoa
    easter = calculate_easter(year)
    carnival_tuesday = easter - timedelta(days=47)
    good_friday = easter - timedelta(days=2)
    corpus_christi = easter + timedelta(days=60)

    holidays[carnival_tuesday] = "Carnaval (Terça-feira)"
    holidays[good_friday] = "Sexta-feira Santa"
    holidays[corpus_christi] = "Corpus Christi"

    return holidays


def is_business_day(d: date, consider_holidays: bool = True) -> bool:
    """Verifica se a data é um dia útil (não cai no fim de semana nem em feriado)."""
    if d.weekday() >= 5:  # Sábado=5, Domingo=6
        return False
    if consider_holidays:
        year_holidays = get_brazilian_holidays(d.year)
        if d in year_holidays:
            return False
    return True


def diff_dates(d1: date, d2: date, consider_holidays: bool = True) -> Dict[str, Any]:
    """Calcula a diferença analítica completa entre duas datas."""
    start = min(d1, d2)
    end = max(d1, d2)
    delta_days = (end - start).days

    # Contagem de dias úteis e feriados no intervalo
    business_days = 0
    weekend_days = 0
    holidays_count = 0
    holidays_in_period: List[Dict[str, Any]] = []

    cur = start
    while cur < end:
        cur += timedelta(days=1)
        if cur.weekday() >= 5:
            weekend_days += 1
        else:
            hols = get_brazilian_holidays(cur.year)
            if consider_holidays and cur in hols:
                holidays_count += 1
                holidays_in_period.append({"date": cur.isoformat(), "name": hols[cur]})
            else:
                business_days += 1

    # Semanas e dias
    weeks = delta_days // 7
    rem_days = delta_days % 7

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_days": delta_days,
        "business_days": business_days,
        "weekend_days": weekend_days,
        "holidays_count": holidays_count,
        "holidays_list": holidays_in_period,
        "weeks": weeks,
        "remaining_days": rem_days,
        "total_hours": delta_days * 24
    }


def add_business_days(start_date: date, days: int, consider_holidays: bool = True) -> date:
    """Adiciona ou subtrai N dias úteis de uma data inicial."""
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    cur = start_date

    while remaining > 0:
        cur += timedelta(days=step)
        if is_business_day(cur, consider_holidays=consider_holidays):
            remaining -= 1

    return cur


def add_calendar_interval(start_date: date, years: int = 0, months: int = 0, days: int = 0) -> date:
    """Soma anos, meses e dias a uma data de calendário."""
    # Calcula novo ano e mês
    total_months = (start_date.year * 12 + (start_date.month - 1)) + (years * 12 + months)
    new_year = total_months // 12
    new_month = (total_months % 12) + 1

    # Trata dias no mês (ex: 31 de janeiro + 1 mês -> 28 de fevereiro)
    max_day_in_new_month = calendar.monthrange(new_year, new_month)[1]
    new_day = min(start_date.day, max_day_in_new_month)

    base = date(new_year, new_month, new_day)
    return base + timedelta(days=days)
