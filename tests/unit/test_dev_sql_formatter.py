"""
Testes unitários rigorosos para o Formatador e Embelezador SQL (dev.sql_formatter).
Validação determinística de indentação, maiúsculas, minificação e proteção de strings literais.
"""
import pytest

from wintoolbox.tools.dev.sql_formatter.logic import (
    format_sql,
    minify_sql,
)
from wintoolbox.tools.dev.sql_formatter.tool import SqlFormatterTool


def test_format_sql_standard_query():
    raw = "select id, nome, email from usuarios where ativo = 1 order by id desc;"
    formatted = format_sql(raw, uppercase_keywords=True, indent_spaces=2)

    assert "SELECT" in formatted
    assert "FROM" in formatted
    assert "WHERE" in formatted
    assert "ORDER BY" in formatted
    assert "DESC" in formatted
    # Verifica quebras de linha nas cláusulas
    lines = [line.strip() for line in formatted.splitlines() if line.strip()]
    assert any(line.startswith("SELECT") for line in lines)
    assert any(line.startswith("FROM") for line in lines)
    assert any(line.startswith("WHERE") for line in lines)


def test_format_sql_preserves_literals_and_comments():
    raw = (
        "-- Comentario de auditoria\n"
        "select u.id, 'select * from tabela_fake' as texto "
        "from usuarios u where u.email = 'dev@test.org';"
    )
    formatted = format_sql(raw, uppercase_keywords=True)

    # A string literal dentro das aspas não deve ser quebrada ou ter seu conteúdo alterado
    assert "'select * from tabela_fake'" in formatted
    assert "'dev@test.org'" in formatted
    assert "-- Comentario de auditoria" in formatted


def test_minify_sql():
    complex_sql = (
        "-- Ignorar esta linha\n"
        "SELECT id,   nome,   email   \n"
        "/* Comentario de bloco */\n"
        "FROM   usuarios   \n"
        "WHERE  ativo = 1   ;"
    )
    minified = minify_sql(complex_sql)
    assert "--" not in minified
    assert "/*" not in minified
    assert "\n" not in minified
    assert minified == "SELECT id,nome,email FROM usuarios WHERE ativo=1;"


def test_sql_formatter_edge_cases():
    assert format_sql("") == ""
    assert minify_sql("") == ""


def test_sql_formatter_tool_ui(qtbot):
    tool = SqlFormatterTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Carrega exemplo pré-definido
    view._load_sample()

    out_text = view._txt_out.toPlainText()
    assert "SELECT" in out_text
    assert "FROM" in out_text
    assert "INNER JOIN" in out_text
    assert "linha(s) formatadas" in view._lbl_status.text()

    # Testa minificação
    view._run_minify()
    min_text = view._txt_out.toPlainText()
    assert "\n" not in min_text
    assert "Minificado:" in view._lbl_status.text()
