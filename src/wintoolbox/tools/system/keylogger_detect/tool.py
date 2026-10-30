"""Interface gráfica do detector de keylogger (Tool)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from wintoolbox.tools.system.keylogger_detect.logic import (
    coletar_dados_keylogger,
    gerar_relatorio_keylogger,
)


@register
class KeyloggerDetectTool(Tool):
    """Detector heurístico de keyloggers e interceptadores de teclado."""

    id = "system.keylogger_detect"
    name = "Detector de Keylogger"
    category = "Segurança e Análise"
    description = (
        "Varre drivers de filtro de teclado, processos e arquivos temporários em busca de "
        "comportamento ou artefatos típicos de keyloggers e gravadores de digitação."
    )
    keywords = [
        "keylogger",
        "teclado",
        "hook",
        "spyware",
        "captura",
        "auditoria",
        "segurança",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return KeyloggerDetectView(self, parent)


class KeyloggerDetectView(PainelFerramenta):
    """Painel do detector heurístico de keylogger."""

    def __init__(self, tool: KeyloggerDetectTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Varredura Antikeylogger", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_varrer = QPushButton("Iniciar Varredura Heurística")
        self.btn_varrer.setProperty("accent", True)
        self.btn_varrer.clicked.connect(self._executar_varredura)
        linha_botoes.addWidget(self.btn_varrer)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Postura
        card_score, lay_score = criar_card("Diagnóstico de Integridade do Teclado", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Integridade: --")
        self.lbl_score.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lay_labels.addWidget(self.lbl_score)

        self.lbl_status = QLabel("Status: Aguardando varredura")
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        lay_labels.addWidget(self.lbl_status)
        lay_labels.addStretch()
        lay_score.addLayout(lay_labels)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v / 100")
        lay_score.addWidget(self.progresso)

        # Tabela de Alertas e Achados
        card_achados, lay_achados = criar_card("Alertas e Evidências Detectadas", self)
        self.adicionar(card_achados)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Severidade", "Evidência / Componente", "Detalhe"])
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setMinimumHeight(130)
        lay_achados.addWidget(self.tabela)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Laudo Técnico de Auditoria", self)
        self.adicionar(card_rel, esticar=1)

        self.txt_relatorio = criar_saida_texto(card_rel)
        lay_rel.addWidget(self.txt_relatorio, stretch=1)

        linha_rodape = QHBoxLayout()
        self.btn_copiar = botao_copiar(self.txt_relatorio, "Copiar Laudo", card_rel)
        linha_rodape.addWidget(self.btn_copiar)

        self.btn_salvar = QPushButton("Salvar Laudo (.txt)")
        self.btn_salvar.clicked.connect(self._salvar_relatorio)
        linha_rodape.addWidget(self.btn_salvar)
        linha_rodape.addStretch()
        lay_rel.addLayout(linha_rodape)

    def _executar_varredura(self) -> None:
        self.btn_varrer.setEnabled(False)
        self.lbl_score.setText("Score de Integridade: Verificando...")
        self.lbl_status.setText("Examinando UpperFilters, processos e logs...")

        def _tarefa() -> Dict[str, Any]:
            return coletar_dados_keylogger()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_varrer.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_seguranca"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Integridade: {score}/100")

            if score >= 85:
                self.lbl_status.setText("Status: Ambiente Seguro (Nenhum Keylogger Detectado)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            elif score >= 60:
                self.lbl_status.setText("Status: Atenção (Filtros de Terceiros Encontrados)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.lbl_status.setText("Status: Risco Alto (Processos ou Logs Suspeitos)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")

            # Preencher tabela
            alertas = resultado.get("alertas", [])
            self.tabela.setRowCount(len(alertas))
            for i, al in enumerate(alertas):
                item_sev = QTableWidgetItem(al["severidade"])
                item_tit = QTableWidgetItem(al["titulo"])
                item_det = QTableWidgetItem(al["detalhe"])
                if al["severidade"] in ("Crítico", "Alto"):
                    item_sev.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tabela.setItem(i, 0, item_sev)
                self.tabela.setItem(i, 1, item_tit)
                self.tabela.setItem(i, 2, item_det)

            relatorio = gerar_relatorio_keylogger(resultado)
            self.txt_relatorio.setPlainText(relatorio)

        def _erro(msg: str) -> None:
            self.btn_varrer.setEnabled(True)
            mostrar_erro(self, "Falha na Varredura", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há laudo para salvar.")
            return
        salvar_texto(self, texto, "Salvar Laudo de Keylogger", "laudo_keylogger.txt")

