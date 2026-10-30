"""Interface gráfica do detector heurístico de rootkits (Tool)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
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
from wintoolbox.tools.system.rootkit_detect.logic import (
    coletar_dados_rootkit,
    gerar_relatorio_rootkit,
)


@register
class RootkitDetectTool(Tool):
    """Detector heurístico de rootkits e processos mascarados."""

    id = "system.rootkit_detect"
    name = "Detector de Rootkit Heurístico"
    category = "Segurança e Análise"
    description = (
        "Analisa processos ocultos comparando APIs nativas do kernel com espaço de usuário, "
        "validação de masquerading em processos críticos e detecção de portas órfãs."
    )
    keywords = [
        "rootkit",
        "processo oculto",
        "masquerading",
        "kernel",
        "auditoria",
        "segurança",
        "forense",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RootkitDetectView(self, parent)


class RootkitDetectView(PainelFerramenta):
    """Painel de visualização e laudo heurístico de rootkits."""

    def __init__(self, tool: RootkitDetectTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Ações de Auditoria", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_varrer = QPushButton("Iniciar Varredura de Rootkits")
        self.btn_varrer.setProperty("accent", True)
        self.btn_varrer.clicked.connect(self._iniciar_varredura)
        linha_botoes.addWidget(self.btn_varrer)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Integridade
        card_score, lay_score = criar_card("Integridade do Sistema e Kernel", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Integridade: --")
        self.lbl_score.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lay_labels.addWidget(self.lbl_score)

        self.lbl_status = QLabel("Status: Aguardando verificação")
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        lay_labels.addWidget(self.lbl_status)
        lay_labels.addStretch()
        lay_score.addLayout(lay_labels)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v / 100")
        lay_score.addWidget(self.progresso)

        # Tabela de Anomalias
        card_tabela, lay_tabela = criar_card("Anomalias e Evidências Detectadas", self)
        self.adicionar(card_tabela)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Severidade", "Tipo de Anomalia", "Detalhes"])
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setMinimumHeight(130)
        lay_tabela.addWidget(self.tabela)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Laudo Pericial de Rootkits", self)
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

    def _iniciar_varredura(self) -> None:
        # Aviso ético de auditoria avançada
        resp = QMessageBox.question(
            self,
            "Auditoria Heurística de Rootkits",
            "Esta ferramenta executa inspeção de baixo nível comparando tabelas de processos e portas.\n\n"
            "Deseja iniciar a varredura defensiva?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self.btn_varrer.setEnabled(False)
        self.lbl_score.setText("Score de Integridade: Auditando...")
        self.lbl_status.setText("Executando cross-check de processos nativos e sockets...")

        def _tarefa() -> Dict[str, Any]:
            return coletar_dados_rootkit()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_varrer.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_integridade"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Integridade: {score}/100")

            if score >= 90:
                self.lbl_status.setText("Status: Íntegro (Sem Processos Ocultos ou Masquerading)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            elif score >= 60:
                self.lbl_status.setText("Status: Atenção (Portas Órfãs ou Inconsistências)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.lbl_status.setText("Status: Risco Crítico (Possível Ocultamento de Processos)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")

            # Preencher tabela
            alertas = resultado.get("alertas", [])
            self.tabela.setRowCount(len(alertas))
            for i, al in enumerate(alertas):
                item_sev = QTableWidgetItem(al["severidade"])
                item_tit = QTableWidgetItem(al["titulo"])
                item_det = QTableWidgetItem(al["detalhe"])
                if al["severidade"] == "Crítico":
                    item_sev.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tabela.setItem(i, 0, item_sev)
                self.tabela.setItem(i, 1, item_tit)
                self.tabela.setItem(i, 2, item_det)

            relatorio = gerar_relatorio_rootkit(resultado)
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
        salvar_texto(self, texto, "Salvar Laudo de Rootkits", "laudo_rootkit.txt")

