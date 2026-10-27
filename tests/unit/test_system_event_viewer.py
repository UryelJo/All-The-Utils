"""
Testes de validação de efeito real para system.event_viewer.logic.
"""
import csv
from pathlib import Path
import pytest

from wintoolbox.tools.system.event_viewer.logic import (
    EventLogRecord,
    parse_winevent_json,
    export_events_to_csv,
    LEVEL_MAP,
)


def test_parse_winevent_json_deterministic():
    sample_json = """
    [
        {
            "Time": "2026-10-25 18:20:00",
            "ProviderName": "Service Control Manager",
            "Id": 7031,
            "Level": 2,
            "Message": "O serviço Spooler terminou inesperadamente.\\r\\nDetalhes do erro."
        },
        {
            "Time": "2026-10-25 18:22:00",
            "ProviderName": "Disk",
            "Id": 153,
            "Level": 3,
            "Message": "A operação de E/S foi repetida no dispositivo de disco."
        }
    ]
    """
    records = parse_winevent_json(sample_json)
    assert len(records) == 2

    r1 = records[0]
    assert r1.time_created == "2026-10-25 18:20:00"
    assert r1.provider_name == "Service Control Manager"
    assert r1.event_id == 7031
    assert r1.level_display == "Erro"
    assert "\r\n" not in r1.message

    r2 = records[1]
    assert r2.event_id == 153
    assert r2.level_display == "Aviso"


def test_parse_winevent_json_edge_cases():
    assert parse_winevent_json("") == []
    assert parse_winevent_json("invalido {") == []


def test_export_events_to_csv_black_box(tmp_path: Path):
    records = [
        EventLogRecord("2026-10-01 10:00:00", "Kernel-Power", 41, "Crítico", "O sistema foi reiniciado sem desligamento prévio."),
        EventLogRecord("2026-10-01 10:05:00", "Ntfs", 55, "Erro", "Uma corrupção de estrutura no sistema de arquivos foi detectada."),
    ]
    csv_file = tmp_path / "logs_export.csv"
    res_path = export_events_to_csv(records, csv_file)

    assert res_path.is_file()
    assert res_path == csv_file
    assert res_path.stat().st_size > 0

    # Validação do Efeito Real: abre com leitor de CSV real e confere integridade
    with open(res_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f, delimiter=";"))
        assert len(reader) == 3  # Cabeçalho + 2 linhas
        assert reader[0] == ["Data e Hora", "Nível", "ID do Evento", "Fonte / Provedor", "Mensagem"]
        assert reader[1][0] == "2026-10-01 10:00:00"
        assert reader[1][1] == "Crítico"
        assert reader[1][2] == "41"
        assert reader[2][1] == "Erro"
