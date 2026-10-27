"""
Lógica pura para emissão de recibos comerciais e propostas de orçamento em PDF.
Inclui algoritmo de conversão de valores monetários em português por extenso e layout ReportLab.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
DEZ_A_DEZENOVE = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]


def _centena_por_extenso(n: int) -> str:
    """Converte um número de 0 a 999 em palavras."""
    if n == 0:
        return ""
    if n == 100:
        return "cem"

    partes = []
    c = n // 100
    d = (n % 100) // 10
    u = n % 10

    if c > 0:
        partes.append(CENTENAS[c])

    if d == 1:
        partes.append(DEZ_A_DEZENOVE[u])
    else:
        if d > 1:
            partes.append(DEZENAS[d])
        if u > 0:
            partes.append(UNIDADES[u])

    return " e ".join(partes)


def numero_para_extenso_reais(valor: float) -> str:
    """
    Converte um valor em reais para texto por extenso (ex: 1250.50 -> 'um mil, duzentos e cinquenta reais e cinquenta centavos').
    Suporta até 999.999.999,99.
    """
    if valor < 0:
        return "valor negativo"
    if valor == 0:
        return "zero reais"

    inteiro = int(round(valor, 2))
    centavos = int(round((round(valor, 2) - inteiro) * 100))

    milhoes = inteiro // 1_000_000
    milhares = (inteiro % 1_000_000) // 1_000
    unidades = inteiro % 1_000

    partes_extenso = []

    if milhoes > 0:
        if milhoes == 1:
            partes_extenso.append("um milhão")
        else:
            partes_extenso.append(f"{_centena_por_extenso(milhoes)} milhões")

    if milhares > 0:
        if milhares == 1:
            partes_extenso.append("um mil")
        else:
            partes_extenso.append(f"{_centena_por_extenso(milhares)} mil")

    if unidades > 0:
        partes_extenso.append(_centena_por_extenso(unidades))

    texto_reais = ", ".join(partes_extenso)
    if inteiro == 1:
        resultado = f"{texto_reais} real"
    elif inteiro > 1:
        resultado = f"{texto_reais} reais"
    else:
        resultado = ""

    if centavos > 0:
        texto_cent = _centena_por_extenso(centavos)
        suffix = "centavo" if centavos == 1 else "centavos"
        if resultado:
            resultado += f" e {texto_cent} {suffix}"
        else:
            resultado = f"{texto_cent} {suffix}"

    return resultado


@dataclass
class ReciboData:
    numero: str
    emissor_nome: str
    emissor_doc: str
    pagador_nome: str
    pagador_doc: str
    valor: float
    referente: str
    cidade: str
    data_emissao: str


@dataclass
class OrcamentoItem:
    descricao: str
    quantidade: float
    valor_unitario: float

    @property
    def total(self) -> float:
        return round(self.quantidade * self.valor_unitario, 2)


@dataclass
class OrcamentoData:
    numero: str
    emissor_nome: str
    emissor_doc: str
    emissor_contato: str
    cliente_nome: str
    cliente_doc: str
    data_emissao: str
    validade_dias: int
    itens: List[OrcamentoItem] = field(default_factory=list)
    observacoes: str = ""


def generate_recibo_pdf(data: ReciboData, output_path: Path) -> Path:
    """Gera um arquivo PDF de recibo comercial diagramado."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReciboTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1E293B"),
        alignment=1  # Centro
    )
    body_style = ParagraphStyle(
        "ReciboBody",
        parent=styles["Normal"],
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#334155")
    )
    bold_style = ParagraphStyle(
        "ReciboBold",
        parent=body_style,
        fontName="Helvetica-Bold"
    )

    valor_fmt = f"R$ {data.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    extenso = numero_para_extenso_reais(data.valor)

    story = [
        Paragraph(f"RECIBO DE PAGAMENTO Nº {data.numero}", title_style),
        Spacer(1, 15),
        Paragraph(f"<b>VALOR: {valor_fmt}</b> ({extenso})", bold_style),
        Spacer(1, 15),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1")),
        Spacer(1, 15),
        Paragraph(
            f"Recebi(emos) de <b>{data.pagador_nome}</b> (CPF/CNPJ: {data.pagador_doc}), "
            f"a quantia de <b>{valor_fmt}</b> ({extenso}), referente a:",
            body_style
        ),
        Spacer(1, 15),
        Paragraph(f"<i>{data.referente}</i>", body_style),
        Spacer(1, 20),
        Paragraph(
            "E, para firmeza e como prova de haver recebido a referida importância, "
            "firmo(amos) o presente recibo para os devidos fins de direito.",
            body_style
        ),
        Spacer(1, 40),
        Paragraph(f"{data.cidade}, {data.data_emissao}", body_style),
        Spacer(1, 40),
        Paragraph("____________________________________________________", ParagraphStyle("AssinaturaLine", alignment=1)),
        Paragraph(f"<b>{data.emissor_nome}</b>", ParagraphStyle("AssinaturaNome", alignment=1)),
        Paragraph(f"CPF/CNPJ: {data.emissor_doc}", ParagraphStyle("AssinaturaDoc", alignment=1))
    ]

    doc.build(story)
    return output_path


def generate_orcamento_pdf(data: OrcamentoData, output_path: Path) -> Path:
    """Gera um arquivo PDF de proposta de orçamento com tabela de itens."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "OrcamentoTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E293B")
    )
    body_style = ParagraphStyle("OrcBody", parent=styles["Normal"], fontSize=10, leading=14)

    story = [
        Paragraph(f"PROPOSTA DE ORÇAMENTO Nº {data.numero}", title_style),
        Spacer(1, 10),
        Paragraph(f"<b>Prestador:</b> {data.emissor_nome} | CNPJ/CPF: {data.emissor_doc} | Contato: {data.emissor_contato}", body_style),
        Paragraph(f"<b>Cliente:</b> {data.cliente_nome} | CNPJ/CPF: {data.cliente_doc}", body_style),
        Paragraph(f"<b>Data:</b> {data.data_emissao} | <b>Validade da Proposta:</b> {data.validade_dias} dias", body_style),
        Spacer(1, 15),
    ]

    # Tabela de itens
    table_data = [["Item / Descrição do Serviço", "Qtd", "Valor Unit. (R$)", "Total (R$)"]]
    total_geral = 0.0

    for item in data.itens:
        tot_item = item.total
        total_geral += tot_item
        unit_fmt = f"R$ {item.valor_unitario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tot_fmt = f"R$ {tot_item:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        table_data.append([item.descricao, f"{item.quantidade:g}", unit_fmt, tot_fmt])

    tot_geral_fmt = f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    table_data.append(["<b>TOTAL GERAL</b>", "", "", f"<b>{tot_geral_fmt}</b>"])

    t = Table(table_data, colWidths=[260, 50, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    story.append(t)

    if data.observacoes.strip():
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>Observações e Condições de Pagamento:</b>", body_style))
        story.append(Paragraph(data.observacoes, body_style))

    doc.build(story)
    return output_path
