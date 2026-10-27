"""
Testes unitários rigorosos (Black-Box Testing) para o conversor de CSV para SQLite (data.csv_to_db).
Validação de banco SQLite físico real, schema inferido e script SQL.
"""
from pathlib import Path
import sqlite3
import pytest

from wintoolbox.tools.data.csv_to_db.logic import (
    csv_to_sql_script,
    csv_to_sqlite,
    detect_delimiter,
    read_csv_data,
    sanitize_identifier,
)
from wintoolbox.tools.data.csv_to_db.tool import CsvToDbTool


def test_sanitize_identifier_and_reserved_words():
    assert sanitize_identifier("Nome do Cliente!") == "nome_do_cliente"
    assert sanitize_identifier("123_coluna") == "col_123_coluna"
    assert sanitize_identifier("SELECT") == "select_val"
    assert sanitize_identifier("WHERE") == "where_val"
    assert sanitize_identifier("   ") == "coluna"


def test_detect_delimiter():
    csv_comma = "id,nome,idade\n1,Carlos,30"
    csv_semi = "id;nome;idade\n1;Carlos;30"
    csv_tab = "id\tnome\tidade\n1\tCarlos\t30"

    assert detect_delimiter(csv_comma) == ","
    assert detect_delimiter(csv_semi) == ";"
    assert detect_delimiter(csv_tab) == "\t"


def test_csv_to_sqlite_roundtrip_blackbox(tmp_path: Path):
    # Cria arquivo CSV com tipos variados: INTEGER, TEXT, REAL, DATE
    csv_content = (
        "id,nome,salario,data_nascimento,ativo\n"
        "1,Ana Paula,4500.50,1990-05-12,true\n"
        "2,Bruno Lima,3200.00,1985-11-20,false\n"
        "3,Carla Dias,7800.75,1995-02-28,true\n"
    )
    csv_file = tmp_path / "funcionarios.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    db_file = tmp_path / "empresa.db"

    # Converte para banco SQLite físico
    res = csv_to_sqlite(csv_file, db_file, table_name="funcionarios")
    assert res["total_rows"] == 3
    assert res["total_columns"] == 5
    assert db_file.is_file()

    # Validação do Efeito Real: Abre o banco gerado e executa queries SQL
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, salario, data_nascimento, ativo FROM funcionarios ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 3
    # Registro 1
    assert rows[0][0] == 1
    assert rows[0][1] == "Ana Paula"
    assert rows[0][2] == 4500.50
    assert rows[0][3] == "1990-05-12"
    assert rows[0][4] == "true" or rows[0][4] == 1  # Aceitável como representação booleana


def test_csv_to_sql_script(tmp_path: Path):
    csv_content = "codigo;produto;preco\n101;Teclado Mecanico;250.00\n102;Mouse Gamer;150.50\n"
    csv_file = tmp_path / "produtos.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    script = csv_to_sql_script(csv_file, table_name="produtos", delimiter=";")
    assert "BEGIN TRANSACTION;" in script
    assert 'CREATE TABLE "produtos"' in script
    assert 'INSERT INTO "produtos"' in script
    assert "Teclado Mecanico" in script
    assert "COMMIT;" in script


def test_csv_to_db_tool_ui(qtbot, tmp_path: Path):
    tool = CsvToDbTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria CSV de teste
    csv_file = tmp_path / "usuarios.csv"
    csv_file.write_text("id,login\n1,admin\n2,gestor\n", encoding="utf-8")

    view._selected_csv_path = csv_file
    view._txt_file_path.setText(str(csv_file))
    view._txt_table_name.setText("usuarios")
    view._reload_csv_preview()

    assert view._schema_table.visible_count() == 2
    assert "2 colunas e 2 linhas identificadas" in view._lbl_status.text()

    # Gera script SQL na UI
    view._on_generate_sql()
    assert 'CREATE TABLE "usuarios"' in view._txt_sql_script.toPlainText()
