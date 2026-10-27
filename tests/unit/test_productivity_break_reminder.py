"""
Testes unitários para o assistente de ergonomia e pausas ativas.
Diretrizes Anti-Gambiarra: Validação real de dados de perfil e asserções determinísticas.
"""
from pathlib import Path
from wintoolbox.tools.productivity.break_reminder.logic import (
    ReminderProfile,
    format_countdown,
    get_random_tip,
    load_reminder_profile,
    save_reminder_profile,
)


def test_format_countdown():
    assert format_countdown(0) == "00:00"
    assert format_countdown(45) == "00:45"
    assert format_countdown(125) == "02:05"
    assert format_countdown(3665) == "01:01:05"
    assert format_countdown(-10) == "00:00"


def test_get_random_tip():
    tip_eye = get_random_tip("eye", index=0)
    assert "Regra 20-20-20" in tip_eye

    tip_stretch = get_random_tip("stretch", index=0)
    assert len(tip_stretch) > 10

    tip_water = get_random_tip("water", index=0)
    assert "água" in tip_water.lower()


def test_reminder_profile_persistence(tmp_path: Path):
    profile = ReminderProfile(
        name="Perfil Home Office",
        eye_interval_min=25,
        eye_duration_sec=30,
        stretch_interval_min=50,
        stretch_duration_sec=90,
        water_interval_min=45,
        eye_enabled=True,
        stretch_enabled=False,
        water_enabled=True
    )
    file_path = tmp_path / "ergonomia_test.json"

    save_reminder_profile(profile, file_path)
    assert file_path.is_file()

    loaded = load_reminder_profile(file_path)
    assert loaded.name == "Perfil Home Office"
    assert loaded.eye_interval_min == 25
    assert loaded.stretch_interval_min == 50
    assert loaded.stretch_enabled is False
    assert loaded.water_enabled is True
