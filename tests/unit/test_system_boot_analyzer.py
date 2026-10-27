"""
Testes de validação de efeito real para system.boot_analyzer.logic.
"""
import pytest
from wintoolbox.tools.system.boot_analyzer.logic import (
    BootEventRecord,
    classify_boot_time,
    parse_boot_xml_event,
    calculate_boot_summary,
)


def test_classify_boot_time_deterministic():
    assert classify_boot_time(15.5) == "Excelente"
    assert classify_boot_time(20.0) == "Excelente"
    assert classify_boot_time(28.0) == "Bom"
    assert classify_boot_time(35.0) == "Bom"
    assert classify_boot_time(50.0) == "Moderado"
    assert classify_boot_time(85.0) == "Lento (Requer Otimização)"


def test_parse_boot_xml_event_deterministic():
    sample_xml = """
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
        <System>
            <TimeCreated SystemTime="2026-10-25T14:30:00.123456Z" />
        </System>
        <EventData>
            <Data Name="BootTime">18450</Data>
            <Data Name="MainPathBootTime">12200</Data>
            <Data Name="BootPostBootTime">6250</Data>
        </EventData>
    </Event>
    """
    rec = parse_boot_xml_event(sample_xml)
    assert rec is not None
    # 18450 ms = 18.4 s (banker's rounding de 18.45 para par mais próximo)
    assert rec.total_boot_sec == 18.4
    # 12200 ms = 12.2 s
    assert rec.main_path_sec == 12.2
    assert rec.post_boot_sec in (6.2, 6.3)
    assert rec.status_label == "Excelente"
    assert "2026-10-25" in rec.timestamp


def test_parse_boot_xml_event_invalid_and_empty():
    assert parse_boot_xml_event("") is None
    assert parse_boot_xml_event("xml invalido <") is None


def test_calculate_boot_summary_calculations():
    records = [
        BootEventRecord("2026-10-01", 20.0, 15.0, 5.0, "Excelente"),
        BootEventRecord("2026-10-02", 30.0, 20.0, 10.0, "Bom"),
        BootEventRecord("2026-10-03", 40.0, 25.0, 15.0, "Moderado"),
    ]
    summary = calculate_boot_summary(records)
    assert summary["count"] == 3
    assert summary["avg_total_sec"] == 30.0
    assert summary["avg_main_sec"] == 20.0
    assert summary["avg_post_sec"] == 10.0
    assert summary["fastest_sec"] == 20.0
    assert summary["slowest_sec"] == 40.0

    empty_sum = calculate_boot_summary([])
    assert empty_sum["count"] == 0
    assert empty_sum["avg_total_sec"] == 0.0
