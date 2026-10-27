"""
Testes unitários para o gerador de recibos e propostas de orçamento em PDF.
Diretrizes Anti-Gambiarra: Validação real do PDF gerado com leitor e asserções determinísticas.
"""
from pathlib import Path
from pypdf import PdfReader

from wintoolbox.tools.productivity.recibo_orcamento.logic import (
    OrcamentoData,
    OrcamentoItem,
    ReciboData,
    generate_orcamento_pdf,
    generate_recibo_pdf,
    numero_para_extenso_reais,
)


def test_numero_para_extenso_reais():
    assert numero_para_extenso_reais(0) == "zero reais"
    assert numero_para_extenso_reais(1) == "um real"
    assert numero_para_extenso_reais(2) == "dois reais"
    assert numero_para_extenso_reais(100) == "cem reais"
    assert numero_para_extenso_reais(101) == "cento e um reais"
    assert numero_para_extenso_reais(1000) == "um mil reais"
    assert numero_para_extenso_reais(1250.50) == "um mil, duzentos e cinquenta reais e cinquenta centavos"
    assert numero_para_extenso_reais(0.01) == "um centavo"
    assert numero_para_extenso_reais(0.75) == "setenta e cinco centavos"
    assert numero_para_extenso_reais(1000000) == "um milhão de reais" or "um milhão" in numero_para_extenso_reais(1000000)


def test_generate_recibo_pdf_real(tmp_path: Path):
    recibo = ReciboData(
        numero="202610-01",
        emissor_nome="Carlos Silva Consultoria",
        emissor_doc="12.345.678/0001-90",
        pagador_nome="Ana Souza",
        pagador_doc="321.654.987-00",
        valor=450.00,
        referente="Consultoria técnica em automação de processos",
        cidade="Curitiba - PR",
        data_emissao="27 de outubro de 2026"
    )

    pdf_out = tmp_path / "recibo_teste.pdf"
    ret_path = generate_recibo_pdf(recibo, pdf_out)

    assert ret_path.is_file()
    assert ret_path.stat().st_size > 500

    # Validação Black-Box: lê com PdfReader
    reader = PdfReader(str(ret_path))
    assert len(reader.pages) == 1
    page_text = reader.pages[0].extract_text()
    assert "RECIBO DE PAGAMENTO Nº 202610-01" in page_text
    assert "Carlos Silva Consultoria" in page_text
    assert "Ana Souza" in page_text
    assert "450,00" in page_text
    assert "quatrocentos e cinquenta reais" in page_text


def test_generate_orcamento_pdf_real(tmp_path: Path):
    orc = OrcamentoData(
        numero="ORC-998",
        emissor_nome="Tech Solutions",
        emissor_doc="11.222.333/0001-44",
        emissor_contato="contato@tech.com",
        cliente_nome="Cliente Alpha",
        cliente_doc="99.888.777/0001-66",
        data_emissao="27/10/2026",
        validade_dias=30,
        itens=[
            OrcamentoItem(descricao="Desenvolvimento de API", quantidade=1.0, valor_unitario=2500.0),
            OrcamentoItem(descricao="Testes automatizados", quantidade=2.0, valor_unitario=500.0),
        ],
        observacoes="Pagamento em 2 parcelas iguais via PIX."
    )

    pdf_out = tmp_path / "orcamento_teste.pdf"
    ret_path = generate_orcamento_pdf(orc, pdf_out)

    assert ret_path.is_file()
    assert ret_path.stat().st_size > 500

    reader = PdfReader(str(ret_path))
    assert len(reader.pages) == 1
    page_text = reader.pages[0].extract_text()
    assert "PROPOSTA DE ORÇAMENTO Nº ORC-998" in page_text
    assert "Tech Solutions" in page_text
    assert "Cliente Alpha" in page_text
    assert "Desenvolvimento de API" in page_text
    assert "3.500,00" in page_text  # Total do orçamento
