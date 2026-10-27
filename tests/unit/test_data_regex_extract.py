"""
Testes unitários rigorosos para a ferramenta Extrator de Dados Estruturados via Regex (data.regex_extract).
Validações exatas de extração, desduplicação, exportação e tratamento de erros.
"""
import pytest

from wintoolbox.tools.data.regex_extract.logic import (
    BUILTIN_PATTERNS,
    export_records_to_text,
    extract_structured_data,
)
from wintoolbox.tools.data.regex_extract.tool import RegexExtractTool


def test_extract_emails_with_deduplication():
    raw_text = (
        "Contato: dev@wintoolbox.com e suporte@wintoolbox.com. "
        "Repetido: DEV@WINTOOLBOX.COM e contato@outro.org."
    )
    pattern = BUILTIN_PATTERNS["emails"]["pattern"]

    # Com deduplicação ativa
    records_dedup = extract_structured_data(raw_text, pattern, deduplicate=True, ignore_case=True)
    assert len(records_dedup) == 3
    emails = [r["value"].lower() for r in records_dedup]
    assert "dev@wintoolbox.com" in emails
    assert "suporte@wintoolbox.com" in emails
    assert "contato@outro.org" in emails

    # Sem deduplicação
    records_all = extract_structured_data(raw_text, pattern, deduplicate=False, ignore_case=True)
    assert len(records_all) == 4


def test_extract_urls_and_ipv4():
    text = (
        "Acesse https://wintoolbox.app/painel e http://192.168.0.1:8080/api. "
        "Servidores DNS: 8.8.8.8 e 1.1.1.1."
    )
    # URLs
    urls = extract_structured_data(text, BUILTIN_PATTERNS["urls"]["pattern"])
    assert len(urls) == 2
    url_vals = [r["value"] for r in urls]
    assert "https://wintoolbox.app/painel" in url_vals
    assert "http://192.168.0.1:8080/api" in url_vals

    # IPv4
    ips = extract_structured_data(text, BUILTIN_PATTERNS["ipv4"]["pattern"])
    assert len(ips) == 3
    ip_vals = [r["value"] for r in ips]
    assert "192.168.0.1" in ip_vals
    assert "8.8.8.8" in ip_vals
    assert "1.1.1.1" in ip_vals


def test_export_records_formats():
    records = [
        {"index": 1, "value": "teste1@mail.com", "type": "E-mails", "position": "0:15", "length": 15},
        {"index": 2, "value": "teste2@mail.com", "type": "E-mails", "position": "20:35", "length": 15},
    ]

    # Lista simples
    list_out = export_records_to_text(records, "list")
    assert list_out == "teste1@mail.com\nteste2@mail.com\n"

    # CSV
    csv_out = export_records_to_text(records, "csv")
    assert "Valor" in csv_out
    assert "teste1@mail.com" in csv_out
    assert "teste2@mail.com" in csv_out

    # JSON
    json_out = export_records_to_text(records, "json")
    assert '"value": "teste1@mail.com"' in json_out


def test_invalid_regex_error():
    with pytest.raises(ValueError, match="Expressão regular inválida"):
        extract_structured_data("texto qualquer", "[aberto-sem-fechar")


def test_regex_extract_tool_ui(qtbot):
    tool = RegexExtractTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Carrega dados de demonstração
    view._load_sample_data()

    # Como o sample tem 2 e-mails únicos (admin@wintoolbox.local e suporte@empresa.com.br repetido)
    assert view._table.visible_count() == 2
    assert "2 registro(s) encontrado(s)" in view._lbl_status.text()
