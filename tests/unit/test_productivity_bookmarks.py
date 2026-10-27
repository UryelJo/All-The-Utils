"""
Testes unitários para o gerenciador de links e favoritos web.
Diretrizes Anti-Gambiarra: Validação real de arquivos HTML/JSON e isolamento estrito de rede.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
from wintoolbox.tools.productivity.bookmarks.logic import (
    Bookmark,
    check_url_status,
    export_netscape_bookmarks_html,
    filter_bookmarks,
    import_netscape_bookmarks_html,
    load_bookmarks_json,
    save_bookmarks_json,
)


def test_filter_bookmarks():
    bookmarks = [
        Bookmark(id="1", title="Python Docs", url="https://docs.python.org", tags=["Dev", "Python"]),
        Bookmark(id="2", title="Fluent Design", url="https://learn.microsoft.com", tags=["Design"]),
        Bookmark(id="3", title="PySide6 Tutorial", url="https://doc.qt.io", tags=["Dev", "Qt"]),
    ]

    # Busca por texto
    res = filter_bookmarks(bookmarks, query="fluent")
    assert len(res) == 1
    assert res[0].id == "2"

    # Filtro por tag
    res_tag = filter_bookmarks(bookmarks, tag="Dev")
    assert len(res_tag) == 2

    # Sem filtro
    assert len(filter_bookmarks(bookmarks)) == 3


def test_import_and_export_netscape_bookmarks_html():
    html_raw = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://docs.python.org" TAGS="Dev,Python">Python Oficial</A>
    <DT><A HREF="https://github.com">GitHub Platform</A>
</DL><p>
"""
    imported = import_netscape_bookmarks_html(html_raw)
    assert len(imported) == 2
    assert imported[0].title == "Python Oficial"
    assert imported[0].url == "https://docs.python.org"
    assert imported[1].title == "GitHub Platform"
    assert imported[1].url == "https://github.com"

    exported_html = export_netscape_bookmarks_html(imported)
    assert "<!DOCTYPE NETSCAPE-Bookmark-file-1>" in exported_html
    assert 'HREF="https://docs.python.org"' in exported_html
    assert "Python Oficial</A>" in exported_html


def test_bookmarks_json_persistence(tmp_path: Path):
    items = [
        Bookmark(id="10", title="Test 1", url="https://example.com", tags=["Exemplo"], notes="Anotação")
    ]
    file_path = tmp_path / "bookmarks_test.json"

    save_bookmarks_json(items, file_path)
    assert file_path.is_file()

    loaded = load_bookmarks_json(file_path)
    assert len(loaded) == 1
    assert loaded[0].id == "10"
    assert loaded[0].title == "Test 1"
    assert loaded[0].notes == "Anotação"


@patch("urllib.request.urlopen")
def test_check_url_status_mocked(mock_urlopen):
    # Simula resposta HTTP 200 OK
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    is_active, code, msg = check_url_status("https://meusite.com")
    assert is_active is True
    assert code == 200
    assert "OK (200)" in msg
