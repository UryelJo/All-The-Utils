"""Detector heurístico de esteganografia LSB em imagens (Tool).

Executa análise estatística multicanal com Chi-quadrado de Pearson (Westfeld-Pfitzmann),
RS Analysis (Fridrich) e Sample Pair Analysis (Dumitrescu), calculando o score consolidado
de probabilidade de dados ocultos e gerando laudo técnico pericial exportável.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import salvar_texto
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    botao_copiar,
    criar_card,
    criar_saida_texto,
    executar_assincrono,
    mostrar_erro,
)
from wintoolbox.tools.crypto.detect_logic import analisar_arquivo, gerar_laudo


@register
class SteganoDetectTool(Tool):
    """Detector heurístico de esteganografia LSB em imagens."""

    id = "crypto.stegano_detect"
    name = "Detector de Esteganografia"
    category = "Segurança e Análise"
    description = (
        "Analisa imagens para detectar anomalias estatísticas e presença provável de "
        "cargas esteganográficas LSB via Chi-quadrado, RS Analysis e Sample Pair Analysis."
    )
    keywords = [
        "esteganografia",
        "stegano",
        "detector",
        "perícia",
        "forense",
        "chi-quadrado",
        "rs-analysis",
        "lsb",
        "análise",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SteganoDetectView(self, parent)


class SteganoDetectView(PainelFerramenta):
    """Interface de análise estatística e laudo de esteganografia."""

    def __init__(self, tool: SteganoDetectTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado_atual: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_arquivo, lay_arquivo = criar_card("Imagem para Análise", self)
        self.adicionar(card_arquivo)

        linha_busca = QHBoxLayout()
        self.txt_caminho = QLineEdit()
        self.txt_caminho.setPlaceholderText("Selecione uma imagem PNG, BMP, TIFF ou JPEG para inspecionar...")
        linha_busca.addWidget(self.txt_caminho, stretch=1)

        self.btn_procurar = QPushButton("Procurar...")
        self.btn_procurar.clicked.connect(self._selecionar_arquivo)
        linha_busca.addWidget(self.btn_procurar)

        self.btn_analisar = QPushButton("Analisar")
        self.btn_analisar.setProperty("accent", True)
        self.btn_analisar.clicked.connect(self._iniciar_analise)
        linha_busca.addWidget(self.btn_analisar)
        lay_arquivo.addLayout(linha_busca)

        # Opções de cálculo
        linha_opcoes = QHBoxLayout()
        self.chk_rs = QCheckBox("Calcular RS Analysis (Fridrich)")
        self.chk_rs.setChecked(True)
        self.chk_pares = QCheckBox("Calcular Sample Pair Analysis (Dumitrescu)")
        self.chk_pares.setChecked(True)
        linha_opcoes.addWidget(self.chk_rs)
        linha_opcoes.addWidget(self.chk_pares)
        linha_opcoes.addStretch()
        lay_arquivo.addLayout(linha_opcoes)

        # Dashboard de Resultado
        card_res, lay_res = criar_card("Diagnóstico e Risco Estimado", self)
        self.adicionar(card_res)

        lay_indicadores = QHBoxLayout()
        self.lbl_score = QLabel("Score de Suspeita: --")
        self.lbl_score.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lay_indicadores.addWidget(self.lbl_score)

        self.lbl_risco = QLabel("Nível: Aguardando análise")
        self.lbl_risco.setFont(QFont("Segoe UI", 11))
        lay_indicadores.addWidget(self.lbl_risco)
        lay_indicadores.addStretch()
        lay_res.addLayout(lay_indicadores)

        self.progresso_score = QProgressBar()
        self.progresso_score.setRange(0, 100)
        self.progresso_score.setValue(0)
        self.progresso_score.setTextVisible(True)
        self.progresso_score.setFormat("%v / 100")
        lay_res.addWidget(self.progresso_score)

        # Laudo Técnico e Detalhes
        card_detalhes, lay_detalhes = criar_card("Laudo Técnico Pericial", self)
        self.adicionar(card_detalhes, esticar=1)

        self.txt_laudo = criar_saida_texto(card_detalhes)
        lay_detalhes.addWidget(self.txt_laudo, stretch=1)

        linha_acoes = QHBoxLayout()
        self.btn_copiar = botao_copiar(self.txt_laudo, "Copiar Laudo", card_detalhes)
        linha_acoes.addWidget(self.btn_copiar)

        self.btn_salvar = QPushButton("Salvar Laudo (.txt)")
        self.btn_salvar.clicked.connect(self._salvar_laudo)
        linha_acoes.addWidget(self.btn_salvar)
        linha_acoes.addStretch()
        lay_detalhes.addLayout(linha_acoes)

    def _selecionar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para Detecção de Esteganografia",
            "",
            "Imagens (*.png *.bmp *.jpg *.jpeg *.tif *.tiff);;Todos os Arquivos (*.*)",
        )
        if caminho:
            self.txt_caminho.setText(caminho)

    def _iniciar_analise(self) -> None:
        caminho_str = self.txt_caminho.text().strip()
        if not caminho_str:
            mostrar_erro(self, "Aviso", "Selecione uma imagem antes de iniciar a análise.")
            return

        caminho = Path(caminho_str)
        if not caminho.exists() or not caminho.is_file():
            mostrar_erro(self, "Erro de Arquivo", f"Arquivo não encontrado: {caminho}")
            return

        calcular_rs = self.chk_rs.isChecked()

        self.btn_analisar.setEnabled(False)
        self.lbl_score.setText("Score de Suspeita: Analisando...")
        self.lbl_risco.setText("Calculando matrizes e testes estatísticos...")

        def _tarefa(ctx: Any = None) -> Dict[str, Any]:
            return analisar_arquivo(caminho, incluir_rs=calcular_rs)

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_analisar.setEnabled(True)
            self._resultado_atual = resultado
            prob = float(resultado.get("probabilidade", 0.0))
            score = int(round(prob if prob > 1.0 else prob * 100))
            nivel = str(resultado.get("rotulo", resultado.get("nivel", "Baixo"))).capitalize()

            self.progresso_score.setValue(score)
            self.lbl_score.setText(f"Score de Suspeita: {score}/100")
            self.lbl_risco.setText(f"Nível de Suspeita: {nivel}")

            if score >= 65:
                self.progresso_score.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")
            elif score >= 35:
                self.progresso_score.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.progresso_score.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")

            laudo = resultado.get("laudo", "") or gerar_laudo(resultado)
            self.txt_laudo.setPlainText(laudo)

        def _erro(msg: str) -> None:
            self.btn_analisar.setEnabled(True)
            self.lbl_score.setText("Score de Suspeita: Falha na análise")
            self.lbl_risco.setText("Ocorreu um erro durante o processamento")
            mostrar_erro(self, "Erro na Análise", f"Não foi possível analisar o arquivo:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_laudo(self) -> None:
        texto = self.txt_laudo.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há laudo técnico disponível para salvar.")
            return
        salvar_texto(self, texto, "Salvar Laudo Pericial de Esteganografia", "laudo_esteganografia.txt")
