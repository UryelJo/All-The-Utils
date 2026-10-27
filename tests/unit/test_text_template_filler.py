"""
Testes unitários rigorosos para a lógica de mala direta e preenchimento de modelos (Template Filler).
Em conformidade estrita com o Princípio da Validação do Efeito Real (Black-Box Testing).
"""
from pathlib import Path
import pytest
from wintoolbox.tools.text.template_filler.logic import (
    apply_modifier,
    extract_placeholders,
    fill_template,
    generate_batch_files,
    parse_csv_data,
)


def test_extract_placeholders_and_modifiers():
    """Valida extração determinística de tags com e sem modificadores."""
    template = "Olá {{nome | title}}, sua chave é {{chave}} e status: {{status|upper}}. Nome de novo: {{nome}}."
    placeholders = extract_placeholders(template)
    assert placeholders == ["nome", "chave", "status"]

    # Modificadores
    assert apply_modifier("maria", "upper") == "MARIA"
    assert apply_modifier("JOAO", "lower") == "joao"
    assert apply_modifier("carlos silva", "title") == "Carlos Silva"
    assert apply_modifier("  teste  ", "strip") == "teste"
    assert apply_modifier("padrao", None) == "padrao"


def test_fill_template_happy_path_and_defaults():
    """Valida preenchimento exato com valores fornecidos e valores padrão para chaves ausentes."""
    template = "Item: {{item | upper}} | Qtd: {{qtd}} | Preço: {{preco}}"
    data = {"item": "notebook", "qtd": 2}
    # "preco" está ausente
    res = fill_template(template, data, default_val="N/A")
    assert res == "Item: NOTEBOOK | Qtd: 2 | Preço: N/A"


def test_parse_csv_comma_and_semicolon():
    """Valida interpretação automática de CSVs com delimitadores vírgula e ponto-e-vírgula."""
    csv_comma = "nome,email,cidade\nAlice,alice@email.com,Curitiba\nBob,bob@email.com,Porto Alegre"
    headers, rows = parse_csv_data(csv_comma)
    assert headers == ["nome", "email", "cidade"]
    assert len(rows) == 2
    assert rows[0] == {"nome": "Alice", "email": "alice@email.com", "cidade": "Curitiba"}
    assert rows[1] == {"nome": "Bob", "email": "bob@email.com", "cidade": "Porto Alegre"}

    csv_semi = "produto;preco;estoque\nMouse;50,00;10\nTeclado;120,00;5"
    headers_semi, rows_semi = parse_csv_data(csv_semi)
    assert headers_semi == ["produto", "preco", "estoque"]
    assert len(rows_semi) == 2
    assert rows_semi[0]["produto"] == "Mouse"
    assert rows_semi[1]["estoque"] == "5"


def test_generate_batch_files_real_disk_effect(tmp_path: Path):
    """
    Validação de Efeito Real em Disco (Black-Box):
    Gera arquivos físicos na pasta temporária e inspeciona se foram gravados
    com nomes corretos e conteúdo interno idêntico ao esperado.
    """
    template = "Recibo #{{index}}\nCliente: {{cliente}}\nValor: R$ {{valor}}"
    records = [
        {"cliente": "Fernando Santos", "valor": "350,00"},
        {"cliente": "Beatriz Lima", "valor": "1.200,50"},
    ]
    out_dir = tmp_path / "recibos_gerados"
    
    generated = generate_batch_files(
        template=template,
        records=records,
        output_dir=out_dir,
        filename_template="recibo_{{index}}_{{cliente}}.txt",
    )

    assert len(generated) == 2
    file_1 = out_dir / "recibo_1_Fernando Santos.txt"
    file_2 = out_dir / "recibo_2_Beatriz Lima.txt"

    assert file_1.exists()
    assert file_2.exists()

    content_1 = file_1.read_text(encoding="utf-8")
    assert content_1 == "Recibo #1\nCliente: Fernando Santos\nValor: R$ 350,00"

    content_2 = file_2.read_text(encoding="utf-8")
    assert content_2 == "Recibo #2\nCliente: Beatriz Lima\nValor: R$ 1.200,50"
