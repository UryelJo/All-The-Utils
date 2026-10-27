"""
Testes unitários para o gerenciador e expansor de trechos de texto (Snippets).
Diretrizes Anti-Gambiarra: Validação real de substituição e asserções determinísticas.
"""
from datetime import datetime
from pathlib import Path
import re
from wintoolbox.tools.productivity.snippets.logic import (
    Snippet,
    expand_snippet_body,
    filter_snippets,
    get_default_snippets,
    load_snippets_from_json,
    save_snippets_to_json,
)


def test_expand_snippet_body():
    body = "Hoje é {date} e agora são {time}. Copiado: [{clipboard}]."
    expanded = expand_snippet_body(body, clipboard_text="Texto Importante")

    today_str = datetime.now().strftime("%Y-%m-%d")
    assert today_str in expanded
    assert "Copiado: [Texto Importante]." in expanded

    uuid_body = "ID: {uuid}"
    exp_uuid = expand_snippet_body(uuid_body)
    assert re.search(r"ID: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", exp_uuid) is not None


def test_filter_snippets():
    snippets = [
        Snippet(id="1", shortcut=":email", title="E-mail Padrão", body="Olá", category="Comunicação"),
        Snippet(id="2", shortcut=":dev", title="Log Dev", body="console.log", category="Dev"),
        Snippet(id="3", shortcut=":hora", title="Hora atual", body="{time}", category="Geral"),
    ]

    # Busca por texto
    res = filter_snippets(snippets, query="console")
    assert len(res) == 1
    assert res[0].id == "2"

    # Filtro por categoria
    res_cat = filter_snippets(snippets, category="Comunicação")
    assert len(res_cat) == 1
    assert res_cat[0].shortcut == ":email"

    # Categoria 'Todas'
    assert len(filter_snippets(snippets, category="Todas")) == 3


def test_snippets_persistence(tmp_path: Path):
    defaults = get_default_snippets()
    file_path = tmp_path / "snippets_teste.json"

    save_snippets_to_json(defaults, file_path)
    assert file_path.is_file()

    loaded = load_snippets_from_json(file_path)
    assert len(loaded) == len(defaults)
    assert loaded[0].shortcut == defaults[0].shortcut
    assert loaded[0].body == defaults[0].body
