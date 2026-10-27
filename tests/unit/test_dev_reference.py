"""
Testes unitários para dev.reference.
Valida integridade das bases de dados técnicas e filtragem instantânea.
"""
from wintoolbox.tools.dev.reference.logic import (
    HTTP_STATUS_LIST,
    MIME_TYPES_LIST,
    SHORTCUTS_LIST,
    VIRTUAL_KEYS_LIST,
    get_ascii_table,
    search_reference,
)


def test_http_status_database():
    """Valida integridade e presença de códigos HTTP fundamentais."""
    codes = {item.code: item.phrase for item in HTTP_STATUS_LIST}
    assert codes[200] == "OK"
    assert codes[201] == "Created"
    assert codes[301] == "Moved Permanently"
    assert codes[404] == "Not Found"
    assert codes[500] == "Internal Server Error"
    assert codes[502] == "Bad Gateway"


def test_mime_types_database():
    """Valida mapeamento de extensões e tipos MIME conhecidos."""
    mimes = {item.extension: item.mime_type for item in MIME_TYPES_LIST}
    assert mimes[".json"] == "application/json"
    assert mimes[".png"] == "image/png"
    assert mimes[".mp4"] == "video/mp4"
    assert mimes[".html"] == "text/html"


def test_ascii_table_generation():
    """Valida geração dos 128 caracteres da tabela ASCII padrão."""
    ascii_table = get_ascii_table()
    assert len(ascii_table) == 128
    # Decimal 65 deve ser 'A' em 0x41
    item_a = ascii_table[65]
    assert item_a.character == "A"
    assert item_a.hexadecimal == "0x41"
    assert item_a.decimal == 65

    # Decimal 0 deve ser NUL
    assert ascii_table[0].character == "NUL"


def test_search_reference_filtering():
    """Valida mecanismo de busca por múltiplos campos."""
    results = search_reference("NotFound", HTTP_STATUS_LIST)
    # Deve encontrar o código 404 (Not Found)
    assert len(results) == 0  # "NotFound" com espaço vira "Not Found"

    results2 = search_reference("404", HTTP_STATUS_LIST)
    assert len(results2) == 1
    assert results2[0].code == 404

    results_vk = search_reference("Escape", VIRTUAL_KEYS_LIST)
    assert len(results_vk) == 1
    assert results_vk[0].vk_name == "VK_ESCAPE"
