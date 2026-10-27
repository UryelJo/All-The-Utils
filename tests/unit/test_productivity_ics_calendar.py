"""
Testes unitários para o manipulador e visualizador de calendário iCalendar (.ics).
Diretrizes Anti-Gambiarra: Validação real de arquivos .ics RFC 5545 e asserções determinísticas.
"""
from pathlib import Path
from wintoolbox.tools.productivity.ics_calendar.logic import (
    CalendarEvent,
    generate_ics_content,
    load_events_from_ics,
    parse_ics_content,
    save_events_to_ics,
)


def test_parse_ics_content():
    ics_raw = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//PT
BEGIN:VEVENT
UID:event-123
SUMMARY:Reunião de Equipe
DTSTART:20261027T140000Z
DTEND:20261027T150000Z
LOCATION:Sala 4B
DESCRIPTION:Alinhamento de cronograma e metas.
END:VEVENT
BEGIN:VEVENT
UID:event-456
SUMMARY:Feriado Municipal
DTSTART:20261102
DTEND:20261102
END:VEVENT
END:VCALENDAR
"""
    events = parse_ics_content(ics_raw)
    assert len(events) == 2

    assert events[0].uid == "event-123"
    assert events[0].summary == "Reunião de Equipe"
    assert events[0].dtstart == "2026-10-27T14:00:00"
    assert events[0].dtend == "2026-10-27T15:00:00"
    assert events[0].location == "Sala 4B"
    assert events[0].description == "Alinhamento de cronograma e metas."
    assert events[0].all_day is False

    assert events[1].uid == "event-456"
    assert events[1].summary == "Feriado Municipal"
    assert events[1].dtstart == "2026-11-02"
    assert events[1].all_day is True


def test_generate_ics_and_file_roundtrip(tmp_path: Path):
    events = [
        CalendarEvent(
            uid="ev-999",
            summary="Lançamento WinToolbox",
            dtstart="2026-11-01T09:00:00",
            dtend="2026-11-01T12:00:00",
            location="Online",
            description="Apresentação das ferramentas operacionais."
        )
    ]

    file_path = tmp_path / "agenda_test.ics"
    save_events_to_ics(events, file_path)
    assert file_path.is_file()

    # Black-box: lê o arquivo .ics salvo e reinterpreta
    reloaded_events = load_events_from_ics(file_path)
    assert len(reloaded_events) == 1
    assert reloaded_events[0].uid == "ev-999"
    assert reloaded_events[0].summary == "Lançamento WinToolbox"
    assert reloaded_events[0].dtstart == "2026-11-01T09:00:00"
    assert reloaded_events[0].dtend == "2026-11-01T12:00:00"
    assert reloaded_events[0].location == "Online"
