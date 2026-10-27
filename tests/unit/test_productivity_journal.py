"""
Testes unitários para o diário de registros pessoais.
Diretrizes Anti-Gambiarra: Validação real de exportação Markdown e asserções determinísticas.
"""
from pathlib import Path
from wintoolbox.tools.productivity.journal.logic import (
    JournalEntry,
    export_journal_to_markdown,
    filter_entries,
    get_entry_by_date,
    load_journal,
    save_journal,
)


def test_journal_entry_operations():
    entries = [
        JournalEntry(id="1", date="2026-10-25", title="Planejamento", content="Início dos trabalhos da semana", mood="😊 Produtivo", tags=["Trabalho"]),
        JournalEntry(id="2", date="2026-10-26", title="Implementação", content="Criados novos componentes Fluent", mood="⚡ Energizado", tags=["Dev", "UI"]),
        JournalEntry(id="3", date="2026-10-27", title="Revisão Geral", content="Testes executados com 100% de sucesso", mood="🌟 Inspirado", tags=["Testes"]),
    ]

    # Obter por data
    e = get_entry_by_date(entries, "2026-10-26")
    assert e is not None
    assert e.title == "Implementação"
    assert e.mood == "⚡ Energizado"

    # Inexistente
    assert get_entry_by_date(entries, "2026-10-01") is None

    # Filtro por busca de texto
    res_search = filter_entries(entries, query="Fluent")
    assert len(res_search) == 1
    assert res_search[0].id == "2"

    # Filtro por intervalo de datas
    res_range = filter_entries(entries, start_date="2026-10-26", end_date="2026-10-27")
    assert len(res_range) == 2


def test_export_journal_to_markdown():
    entries = [
        JournalEntry(id="1", date="2026-10-27", title="Dia Produtivo", content="Conclusão dos módulos com testes.", mood="😊 Produtivo", tags=["Trabalho"])
    ]

    md_content = export_journal_to_markdown(entries, journal_title="Diário Pessoal de Teste")
    assert "# Diário Pessoal de Teste" in md_content
    assert "## 27/10/2026" in md_content
    assert "Dia Produtivo" in md_content
    assert "**Humor:** 😊 Produtivo" in md_content
    assert "Conclusão dos módulos com testes." in md_content


def test_journal_persistence(tmp_path: Path):
    entries = [
        JournalEntry(id="100", date="2026-10-27", title="Teste Persistência", content="Conteúdo salvo", mood="😐 Neutro")
    ]
    file_path = tmp_path / "journal_test.json"

    save_journal(entries, file_path)
    assert file_path.is_file()

    loaded = load_journal(file_path)
    assert len(loaded) == 1
    assert loaded[0].id == "100"
    assert loaded[0].title == "Teste Persistência"
    assert loaded[0].content == "Conteúdo salvo"
