"""
Lógica pura da ferramenta Conversor de Timestamps e Bases Numéricas.
Permite converter Unix Epoch e alternar entre binário, octal, decimal e hexadecimal sem Qt.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class TimestampConversionResult:
    is_valid: bool
    local_str: str
    utc_str: str
    iso_str: str


@dataclass
class NumberBasesResult:
    is_valid: bool
    decimal: str
    hexadecimal: str
    binary: str
    octal: str


def convert_epoch_to_dates(epoch_str: str) -> TimestampConversionResult:
    """Converte string de timestamp epoch (em segundos ou milissegundos) em datas formatadas."""
    cleaned = epoch_str.strip()
    if not cleaned.isdigit():
        return TimestampConversionResult(
            is_valid=False,
            local_str="Timestamp inválido.",
            utc_str="-",
            iso_str="-",
        )

    ts = float(cleaned)
    if len(cleaned) > 10:
        ts = ts / 1000.0

    try:
        dt_local = datetime.fromtimestamp(ts)
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return TimestampConversionResult(
            is_valid=True,
            local_str=dt_local.strftime("%d/%m/%Y %H:%M:%S"),
            utc_str=dt_utc.strftime("%d/%m/%Y %H:%M:%S UTC"),
            iso_str=dt_utc.isoformat(),
        )
    except Exception:
        return TimestampConversionResult(
            is_valid=False,
            local_str="Data fora do intervalo suportado.",
            utc_str="-",
            iso_str="-",
        )


def convert_datetime_to_epoch(dt: datetime) -> int:
    """Retorna o timestamp em segundos a partir de um datetime."""
    return int(dt.timestamp())


def convert_number_bases(value_str: str, base: int) -> NumberBasesResult:
    """Converte um número informado na base fornecida (2, 8, 10, 16) para as demais bases."""
    clean = value_str.strip().replace(" ", "").replace("_", "")
    if not clean:
        return NumberBasesResult(
            is_valid=False,
            decimal="",
            hexadecimal="",
            binary="",
            octal="",
        )

    try:
        num = int(clean, base)
        return NumberBasesResult(
            is_valid=True,
            decimal=str(num),
            hexadecimal=hex(num)[2:].upper(),
            binary=bin(num)[2:],
            octal=oct(num)[2:],
        )
    except ValueError:
        return NumberBasesResult(
            is_valid=False,
            decimal="",
            hexadecimal="",
            binary="",
            octal="",
        )
