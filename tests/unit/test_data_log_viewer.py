"""
Testes unitários rigorosos para data.log_viewer.logic.
Garante leitura otimizada de tail, identificação precisa de níveis de severidade e filtros por regex.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.data.log_viewer.logic import (
    filter_log_records,
    get_file_info,
    parse_log_line,
    read_tail_lines,
)


def test_get_file_info(tmp_path: Path):
    f = tmp_path / "app.log"
    f.write_text("Linha 1\nLinha 2\n", encoding="utf-8")

    info = get_file_info(str(f))
    assert info["exists"] is True
    assert info["name"] == "app.log"
    assert info["size_bytes"] > 0
    assert "B" in info["size_formatted"]

    info_none = get_file_info(str(tmp_path / "inexistente.log"))
    assert info_none["exists"] is False
    assert info_none["size_bytes"] == 0


def test_read_tail_lines(tmp_path: Path):
    f = tmp_path / "multi_lines.log"
    lines = [f"2026-10-27 10:00:{i:02d} [INFO] Mensagem {i}" for i in range(100)]
    f.write_text("\n".join(lines), encoding="utf-8")

    tail_20 = read_tail_lines(str(f), max_lines=20)
    assert len(tail_20) == 20
    assert "Mensagem 80" in tail_20[0]
    assert "Mensagem 99" in tail_20[-1]


def test_parse_log_line_and_filter():
    lines = [
        "2026-10-27 10:05:01 [DEBUG] Conexão com banco aberta",
        "2026-10-27 10:05:02 [INFO] Usuário autenticado com sucesso",
        "2026-10-27 10:05:03 [WARNING] Timeout de rede detectado, tentando novamente",
        "2026-10-27 10:05:04 [ERROR] Falha crítica de I/O no disco D:",
        "2026-10-27 10:05:05 [CRITICAL] Aplicação finalizada inesperadamente",
    ]
    records = [parse_log_line(l) for l in lines]

    assert records[0]["level"] == "DEBUG"
    assert records[0]["timestamp"] == "2026-10-27 10:05:01"

    assert records[1]["level"] == "INFO"
    assert records[2]["level"] == "WARN"  # mapeado de WARNING
    assert records[3]["level"] == "ERROR"
    assert records[4]["level"] == "FATAL"  # mapeado de CRITICAL

    # Filtro por nível ERROR
    f_err = filter_log_records(records, level_filter="ERROR")
    assert len(f_err) == 1
    assert "Falha crítica" in f_err[0]["message"]

    # Filtro por texto
    f_txt = filter_log_records(records, text_query="autenticado")
    assert len(f_txt) == 1
    assert f_txt[0]["level"] == "INFO"

    # Filtro por regex
    f_reg = filter_log_records(records, text_query=r"disco [A-Z]:", is_regex=True)
    assert len(f_reg) == 1
    assert "disco D:" in f_reg[0]["message"]

    # Sem filtros (ALL)
    f_all = filter_log_records(records, level_filter="ALL")
    assert len(f_all) == 5
