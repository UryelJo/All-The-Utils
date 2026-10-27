"""
Testes unitários rigorosos para a ferramenta de Entidades HTML (encode.html_entities).
Validações de codificação nomeada, decimal, hex, decodificação e catálogo.
"""
import pytest

from wintoolbox.tools.encode.html_entities.logic import (
    COMMON_ENTITIES,
    decode_html,
    encode_html,
    filter_catalog,
)
from wintoolbox.tools.encode.html_entities.tool import HtmlEntitiesTool


def test_encode_html_modes_deterministic():
    text = '<div class="teste">João & Maria © 2026</div>'

    # 1. Modo Nomeada (Named)
    encoded_named = encode_html(text, mode="named")
    assert "&lt;div class=&quot;teste&quot;&gt;" in encoded_named
    assert "&amp;" in encoded_named
    assert "&copy;" in encoded_named

    # 2. Modo Decimal
    encoded_dec = encode_html("<>&", mode="decimal")
    assert encoded_dec == "&#60;&#62;&#38;"

    # 3. Modo Hexadecimal
    encoded_hex = encode_html("<>&©", mode="hex")
    assert encoded_hex == "&#x3C;&#x3E;&#x26;&#xA9;"


def test_encode_html_only_reserved():
    text = 'Café com açúcar <script>alert("1 & 2")</script>'
    # Com only_reserved=True, 'é', 'ú', 'ç' permanecem inalterados, apenas '<', '>', '&', '"' viram entidades
    encoded = encode_html(text, mode="named", only_reserved=True)
    assert "Café com açúcar" in encoded
    assert "&lt;script&gt;" in encoded
    assert "&quot;1 &amp; 2&quot;" in encoded


def test_decode_html_mixed_entities():
    # Mescla entidades nomeadas, decimais e hexadecimais
    mixed = "&lt;b&gt;Pre&ccedil;o: &#8364; 100 &#x26; Frete Gr&aacute;tis &copy;&lt;/b&gt;"
    decoded = decode_html(mixed)
    assert decoded == "<b>Preço: € 100 & Frete Grátis ©</b>"

    # String vazia
    assert decode_html("") == ""
    assert encode_html("") == ""


def test_catalog_filter():
    # Busca por "Euro"
    res_euro = filter_catalog("Euro")
    assert len(res_euro) == 1
    assert res_euro[0]["char"] == "€"
    assert res_euro[0]["name"] == "&euro;"

    # Busca por símbolo &
    res_amp = filter_catalog("&amp;")
    assert len(res_amp) >= 1
    assert res_amp[0]["char"] == "&"

    # Busca vazia deve retornar todo o catálogo
    assert len(filter_catalog("")) == len(COMMON_ENTITIES)


def test_html_entities_tool_ui(qtbot):
    tool = HtmlEntitiesTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Simula codificação
    view._txt_in.setPlainText("<b>Teste & 123</b>")
    view._on_encode()
    assert "&lt;b&gt;Teste &amp; 123&lt;/b&gt;" == view._txt_out.toPlainText()

    # Simula decodificação
    view._txt_in.setPlainText("&copy; 2026")
    view._on_decode()
    assert "© 2026" == view._txt_out.toPlainText()

    # Testa filtro na aba de catálogo
    view._on_search_catalog("copyright")
    assert view._catalog_table.visible_count() == 1
    assert view._catalog_table.source_model.record_at(0)["char"] == "©"
