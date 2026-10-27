"""
Testes unitários para o painel de contagem regressiva e cálculo de prazos.
Diretrizes Anti-Gambiarra: Validação real de tempo e asserções determinísticas.
"""
from datetime import datetime, timedelta
from pathlib import Path
from wintoolbox.tools.productivity.countdown.logic import (
    CountdownItem,
    calculate_time_remaining,
    get_default_countdowns,
    load_countdowns,
    save_countdowns,
)


def test_calculate_time_remaining_future():
    ref_dt = datetime(2026, 10, 27, 12, 0, 0)
    target_dt = datetime(2026, 10, 29, 15, 30, 45)

    res = calculate_time_remaining(target_dt.isoformat(), reference_dt=ref_dt)
    assert res["is_past"] is False
    assert res["days"] == 2
    assert res["hours"] == 3
    assert res["minutes"] == 30
    assert res["seconds"] == 45
    assert res["formatted"] == "2d 03h 30m 45s"


def test_calculate_time_remaining_past():
    ref_dt = datetime(2026, 10, 27, 12, 0, 0)
    target_dt = datetime(2026, 10, 25, 10, 0, 0)

    res = calculate_time_remaining(target_dt.isoformat(), reference_dt=ref_dt)
    assert res["is_past"] is True
    assert res["days"] == 2
    assert res["hours"] == 2
    assert "Concluído há 2d 2h" in res["formatted"]


def test_countdown_persistence(tmp_path: Path):
    items = [
        CountdownItem(id="1", title="Evento A", target_datetime="2026-12-31T23:59:59", category="Ano Novo", color="#eab308"),
        CountdownItem(id="2", title="Evento B", target_datetime="2026-11-15T10:00:00", category="Trabalho", color="#3b82f6"),
    ]
    file_path = tmp_path / "countdown_test.json"

    save_countdowns(items, file_path)
    assert file_path.is_file()

    loaded = load_countdowns(file_path)
    assert len(loaded) == 2
    assert loaded[0].title == "Evento A"
    assert loaded[0].category == "Ano Novo"
    assert loaded[1].title == "Evento B"
    assert loaded[1].color == "#3b82f6"
