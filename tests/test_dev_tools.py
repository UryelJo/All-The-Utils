"""
Testes unitários das ferramentas de Desenvolvimento (Fase 9).
Testa a lógica de:
- dev.fake_data
- dev.sqlite_viewer
- dev.color_converter
- dev.cron_calculator
- dev.pyinstaller_wrapper
- dev.project_scaffold
"""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import pytest

# 1. Fake Data
from wintoolbox.tools.dev.fake_data.logic import (
    generate_cnpj, generate_cpf, generate_dataset,
    generate_lorem_ipsum, export_dataset
)

# 2. SQLite Viewer
from wintoolbox.tools.dev.sqlite_viewer.logic import (
    export_query_results, execute_query, get_table_schema, list_tables_and_views
)

# 3. Color Converter
from wintoolbox.tools.dev.color_converter.logic import (
    cmyk_to_rgb, contrast_ratio, get_all_color_formats, hsl_to_rgb,
    parse_hex_color, relative_luminance, rgb_to_cmyk, rgb_to_hex,
    rgb_to_hsl, rgb_to_hsv
)

# 4. Cron Calculator
from wintoolbox.tools.dev.cron_calculator.logic import (
    explain_cron, get_next_cron_occurrences, parse_cron
)

# 5. PyInstaller Wrapper
from wintoolbox.tools.dev.pyinstaller_wrapper.logic import (
    build_batch_script, build_pyinstaller_command, check_pyinstaller_available,
    validate_compilation_inputs
)

# 6. Project Scaffold
from wintoolbox.tools.dev.project_scaffold.logic import (
    generate_scaffold_files, get_available_languages, get_available_licenses,
    get_gitignore_content, get_license_content, get_readme_content
)


# ==========================================
# TESTES: 1. Fake Data
# ==========================================
def test_fake_data_cpf_and_cnpj():
    cpf_fmt = generate_cpf(formatted=True)
    assert len(cpf_fmt) == 14
    assert cpf_fmt[3] == "." and cpf_fmt[7] == "." and cpf_fmt[11] == "-"

    cpf_raw = generate_cpf(formatted=False)
    assert len(cpf_raw) == 11
    assert cpf_raw.isdigit()

    cnpj_fmt = generate_cnpj(formatted=True)
    assert len(cnpj_fmt) == 18
    assert cnpj_fmt[2] == "." and cnpj_fmt[6] == "." and cnpj_fmt[10] == "/" and cnpj_fmt[15] == "-"

    cnpj_raw = generate_cnpj(formatted=False)
    assert len(cnpj_raw) == 14
    assert cnpj_raw.isdigit()


def test_fake_data_dataset_generation_and_export():
    fields = ["nome", "cpf", "email", "empresa", "cidade", "uuid"]
    data = generate_dataset(fields=fields, count=5)
    assert len(data) == 5
    for row in data:
        for f in fields:
            assert f in row
            assert row[f] is not None

    # Exportação JSON
    json_out = export_dataset(data, format_type="json")
    parsed = json.loads(json_out)
    assert len(parsed) == 5

    # Exportação CSV (separador ';' padrão pt-BR/Excel)
    csv_out = export_dataset(data, format_type="csv")
    assert "nome;cpf;email" in csv_out

    # Exportação SQL
    sql_out = export_dataset(data, format_type="sql", table_name="usuarios")
    assert "INSERT INTO `usuarios`" in sql_out

    # Lorem Ipsum
    lorem = generate_lorem_ipsum(count=2, unit="paragraphs")
    paras = lorem.split("\n\n")
    assert len(paras) == 2


# ==========================================
# TESTES: 2. SQLite Viewer
# ==========================================
def test_sqlite_viewer_logic(tmp_path: Path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT, saldo REAL)")
    cursor.execute("INSERT INTO clientes (nome, saldo) VALUES ('Alice', 1500.50), ('Bob', 320.0)")
    conn.commit()
    conn.close()

    # Listar tabelas
    tables = list_tables_and_views(db_file)
    table_names = [t["name"] for t in tables]
    assert "clientes" in table_names

    # Esquema
    schema = get_table_schema(db_file, "clientes")
    assert len(schema) == 3
    assert schema[0]["name"] == "id"
    assert schema[1]["name"] == "nome"

    # Consulta
    cols, rows, elapsed = execute_query(db_file, "SELECT * FROM clientes ORDER BY id", max_rows=10)
    assert cols == ["id", "nome", "saldo"]
    assert len(rows) == 2
    assert rows[0]["nome"] == "Alice"
    assert rows[1]["nome"] == "Bob"
    assert elapsed >= 0.0

    # Exportação
    csv_res = export_query_results(rows, format_type="csv")
    assert "id;nome;saldo" in csv_res
    assert "Alice" in csv_res

    json_res = export_query_results(rows, format_type="json")
    loaded = json.loads(json_res)
    assert len(loaded) == 2
    assert loaded[0]["saldo"] == 1500.50



# ==========================================
# TESTES: 3. Color Converter
# ==========================================
def test_color_converter_logic():
    # Parse HEX
    r, g, b, a = parse_hex_color("#2563EB")
    assert (r, g, b) == (37, 99, 235)
    assert a == 1.0

    r, g, b, a = parse_hex_color("#FFF")
    assert (r, g, b) == (255, 255, 255)

    # Conversões
    hex_str = rgb_to_hex(255, 0, 0)
    assert hex_str.upper() == "#FF0000"

    h, s, l = rgb_to_hsl(255, 0, 0)
    assert (h, s, l) == (0, 100, 50)

    rgb = hsl_to_rgb(0, 100, 50)
    assert rgb == (255, 0, 0)

    c, m, y, k = rgb_to_cmyk(255, 0, 0)
    assert (c, m, y, k) == (0, 100, 100, 0)

    rgb_cmyk = cmyk_to_rgb(0, 100, 100, 0)
    assert rgb_cmyk == (255, 0, 0)

    # Contraste WCAG (preto x branco = 21.0)
    contrast = contrast_ratio((0, 0, 0), (255, 255, 255))
    assert contrast == 21.0

    # Formatos consolidados
    data = get_all_color_formats(37, 99, 235)
    assert data["hex"].upper() == "#2563EB"
    assert "CSS RGB" in data["code_snippets"]
    assert "Tailwind" in data["code_snippets"]


# ==========================================
# TESTES: 4. Cron Calculator
# ==========================================
def test_cron_calculator_logic():
    min_set, hr_set, dom_set, mon_set, dow_set, sec_set = parse_cron("*/15 9-18 * * 1-5")
    assert min_set == {0, 15, 30, 45}
    assert 9 in hr_set and 18 in hr_set and 8 not in hr_set
    assert dow_set == {1, 2, 3, 4, 5}
    assert sec_set is None

    exp = explain_cron("0 0 * * *")
    assert "meia-noite" in exp.lower()

    # Próximas datas
    ref_time = datetime(2026, 1, 1, 12, 0, 0)
    dates = get_next_cron_occurrences("0 * * * *", count=3, start_time=ref_time)
    assert len(dates) == 3
    assert dates[0] == datetime(2026, 1, 1, 13, 0, 0)
    assert dates[1] == datetime(2026, 1, 1, 14, 0, 0)
    assert dates[2] == datetime(2026, 1, 1, 15, 0, 0)


# ==========================================
# TESTES: 5. PyInstaller Wrapper
# ==========================================
def test_pyinstaller_wrapper_logic(tmp_path: Path):
    cmd = build_pyinstaller_command(
        script_path="C:/app/main.py",
        app_name="SuperApp",
        onefile=True,
        windowed=True,
        icon_path="C:/app/icon.ico",
        add_data=["assets;assets"],
        hidden_imports=["sqlite3"]
    )
    assert "-m" in cmd and "PyInstaller" in cmd
    assert "--onefile" in cmd
    assert "--windowed" in cmd
    assert "--name" in cmd and "SuperApp" in cmd
    assert "--icon" in cmd and "C:/app/icon.ico" in cmd
    assert "--add-data" in cmd and "assets;assets" in cmd
    assert "--hidden-import" in cmd and "sqlite3" in cmd
    assert "C:/app/main.py" in cmd

    bat = build_batch_script(cmd, project_dir="C:/app")
    assert "cd /d \"C:/app\"" in bat
    assert "@echo off" in bat

    # Validação de entradas
    fake_script = tmp_path / "app.py"
    fake_script.write_text("print('ok')")
    errs = validate_compilation_inputs(str(fake_script), icon_path=None)
    assert len(errs) == 0

    errs_missing = validate_compilation_inputs("arquivo_inexistente.py")
    assert len(errs_missing) > 0


# ==========================================
# TESTES: 6. Project Scaffold
# ==========================================
def test_project_scaffold_logic(tmp_path: Path):
    langs = get_available_languages()
    assert "Python" in langs
    assert "Node.js / TypeScript" in langs

    licenses = get_available_licenses()
    assert "MIT" in licenses
    assert "Apache 2.0" in licenses

    # Conteúdo gerado
    git_py = get_gitignore_content("Python", include_general=True)
    assert "__pycache__/" in git_py
    assert ".vscode/" in git_py

    mit = get_license_content("MIT", "Uryel Dev", year=2026)
    assert "2026 Uryel Dev" in mit
    assert "MIT License" in mit

    readme = get_readme_content("WinToolbox", "Canivete suíço para Windows", "Uryel", "MIT")
    assert "# WinToolbox" in readme
    assert "MIT" in readme

    # Criação em disco
    scaffold_dir = tmp_path / "novo_projeto"
    results = generate_scaffold_files(
        target_dir=scaffold_dir,
        project_name="NovoApp",
        description="Um app de teste",
        author="Dev",
        language="Python",
        license_type="MIT",
        create_gitignore=True,
        create_license=True,
        create_readme=True,
        create_editorconfig=True,
        create_env_example=True
    )

    created_files = [f[0] for f in results]
    assert ".gitignore" in created_files
    assert "LICENSE" in created_files
    assert "README.md" in created_files
    assert ".editorconfig" in created_files
    assert ".env.example" in created_files

    assert (scaffold_dir / ".gitignore").exists()
    assert (scaffold_dir / "LICENSE").exists()
