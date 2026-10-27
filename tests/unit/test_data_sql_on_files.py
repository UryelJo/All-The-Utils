"""
Testes unitários rigorosos para data.sql_on_files.logic.
Garante execução determinística de queries SQL, importação precisa de CSV e JSON e exportações de relatórios.
"""
import json
from pathlib import Path
import sqlite3
import pytest
from wintoolbox.tools.data.sql_on_files.logic import (
    execute_sql_query,
    export_query_results,
    import_csv_to_sqlite,
    import_json_to_sqlite,
    infer_column_type,
    sanitize_table_name,
)


def test_sanitize_table_name_and_type_inference():
    assert sanitize_table_name("Minha Tabela 2026!") == "minha_tabela_2026_"
    assert sanitize_table_name("123tabela") == "t_123tabela"
    assert sanitize_table_name("clientes-sp") == "clientes_sp"

    assert infer_column_type(["1", "20", "300"]) == "INTEGER"
    assert infer_column_type(["1.5", "2,8", "3"]) == "REAL"
    assert infer_column_type(["texto", "10", "abc"]) == "TEXT"
    assert infer_column_type(["", "   "]) == "TEXT"


def test_import_csv_and_query(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    csv_file = tmp_path / "vendas.csv"
    csv_file.write_text(
        "id,produto,quantidade,preco_unitario\n"
        "1,Notebook,2,4500.50\n"
        "2,Mouse,10,120.00\n"
        "3,Teclado,5,250.00\n",
        encoding="utf-8",
    )

    res_import = import_csv_to_sqlite(conn, str(csv_file), table_name="tb_vendas")
    assert res_import["table_name"] == "tb_vendas"
    assert res_import["row_count"] == 3
    assert res_import["columns"] == ["id", "produto", "quantidade", "preco_unitario"]

    # Consulta de agregação
    q_agg = "SELECT produto, quantidade * preco_unitario AS total FROM tb_vendas ORDER BY id ASC;"
    res_q = execute_sql_query(conn, q_agg)
    assert res_q["error"] == ""
    assert res_q["columns"] == ["produto", "total"]
    assert res_q["row_count"] == 3
    assert res_q["rows"][0] == ["Notebook", "9001.0"]
    assert res_q["rows"][1] == ["Mouse", "1200.0"]
    assert res_q["rows"][2] == ["Teclado", "1250.0"]

    conn.close()


def test_import_json_and_query(tmp_path: Path):
    conn = sqlite3.connect(":memory:")
    json_file = tmp_path / "usuarios.json"
    users_data = [
        {"id": 101, "nome": "Alice", "departamento": "Engenharia", "ativo": True},
        {"id": 102, "nome": "Bruno", "departamento": "Produto", "ativo": False},
        {"id": 103, "nome": "Carla", "departamento": "Engenharia", "ativo": True},
    ]
    json_file.write_text(json.dumps(users_data), encoding="utf-8")

    res_import = import_json_to_sqlite(conn, str(json_file), table_name="usuarios")
    assert res_import["table_name"] == "usuarios"
    assert res_import["row_count"] == 3

    # Query com WHERE
    q = "SELECT nome FROM usuarios WHERE departamento = 'Engenharia' ORDER BY id DESC;"
    res_q = execute_sql_query(conn, q)
    assert res_q["error"] == ""
    assert res_q["rows"] == [["Carla"], ["Alice"]]

    conn.close()


def test_execute_sql_syntax_error_and_dml():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE teste (id INT);")

    # Syntax Error
    res_err = execute_sql_query(conn, "SELECT FROM WHERE")
    assert "syntax error" in res_err["error"].lower()
    assert res_err["rows"] == []

    # DML (INSERT)
    res_dml = execute_sql_query(conn, "INSERT INTO teste VALUES (1), (2);")
    assert res_dml["error"] == ""
    assert res_dml["row_count"] == 2

    # Query vazia
    res_empty = execute_sql_query(conn, "   ")
    assert res_empty["error"] == "Consulta SQL vazia."

    conn.close()


def test_export_query_results():
    cols = ["Nome", "Cargo"]
    rows = [["Ana", "Diretora"], ["Beto", "Analista"]]

    # CSV
    csv_out = export_query_results(cols, rows, "csv")
    assert "Nome;Cargo" in csv_out
    assert "Ana;Diretora" in csv_out

    # JSON
    json_out = export_query_results(cols, rows, "json")
    parsed = json.loads(json_out)
    assert len(parsed) == 2
    assert parsed[0] == {"Nome": "Ana", "Cargo": "Diretora"}

    # Markdown
    md_out = export_query_results(cols, rows, "markdown")
    assert "| Nome | Cargo |" in md_out
    assert "| Ana | Diretora |" in md_out

    # HTML
    html_out = export_query_results(cols, rows, "html")
    assert "<th>Nome</th>" in html_out
    assert "<td>Diretora</td>" in html_out
