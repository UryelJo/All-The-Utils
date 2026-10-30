"""Interface gráfica da auditoria do Windows Defender (Tool)."""
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
from wintoolbox.tools.system.defender_audit.logic import (
    coletar_status_defender,
    gerar_relatorio_defender,
)


@register
class DefenderAuditTool(Tool):
    """Auditoria defensiva do Microsoft Defender Antivirus."""

    id = "system.defender_audit"
    name = "Auditoria do Windows Defender"
    category = "Segurança e Análise"
    description = (
        "Audita o status do Microsoft Defender Antivirus, proteção em tempo real, "
        "regras ASR, data de assinaturas e lista de exclusões ativas."
    )
    keywords = [
        "defender",
        "antivirus",
        "segurança",
        "auditoria",
        "exclusões",
        "proteção",
        "conformidade",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DefenderAuditView(self, parent)


class DefenderAuditView(PainelFerramenta):
    """Painel de visualização e laudo do Windows Defender."""

    def __init__(self, tool: DefenderAuditTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        # Ações do Topo
        card_acoes, lay_acoes = criar_card("Ações de Auditoria", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_auditar = QPushButton("Executar Auditoria do Defender")
        self.btn_auditar.setProperty("accent", True)
        self.btn_auditar.clicked.connect(self._executar_auditoria)
        linha_botoes.addWidget(self.btn_auditar)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Postura
        card_score, lay_score = criar_card("Postura de Proteção e Conformidade", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Segurança: --")
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

        # Tabela de Alertas
        card_alertas, lay_alertas = criar_card("Alertas e Riscos Detectados", self)
        self.adicionar(card_alertas)

        self.tabela_alertas = QTableWidget(0, 3)
        self.tabela_alertas.setHorizontalHeaderLabels(["Severidade", "Item / Configuração", "Detalhe do Risco"])
        self.tabela_alertas.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela_alertas.setAlternatingRowColors(True)
        self.tabela_alertas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_alertas.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela_alertas.setMinimumHeight(130)
        lay_alertas.addWidget(self.tabela_alertas)

        # Relatório Técnico Completo
        card_rel, lay_rel = criar_card("Relatório Técnico de Conformidade", self)
        self.adicionar(card_rel, esticar=1)

        self.txt_relatorio = criar_saida_texto(card_rel)
        lay_rel.addWidget(self.txt_relatorio, stretch=1)

        linha_rodape = QHBoxLayout()
        self.btn_copiar = botao_copiar(self.txt_relatorio, "Copiar Relatório", card_rel)
        linha_rodape.addWidget(self.btn_copiar)

        self.btn_salvar = QPushButton("Salvar Relatório (.txt)")
        self.btn_salvar.clicked.connect(self._salvar_relatorio)
        linha_rodape.addWidget(self.btn_salvar)
        linha_rodape.addStretch()
        lay_rel.addLayout(linha_rodape)

    def _executar_auditoria(self) -> None:
        self.btn_auditar.setEnabled(False)
        self.lbl_score.setText("Score de Segurança: Auditando...")
        self.lbl_status.setText("Consultando WMI e PowerShell...")

        def _tarefa(ctx: Any = None) -> Dict[str, Any]:
            return coletar_status_defender()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_auditar.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_conformidade"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Segurança: {score}/100")

            if score >= 80:
                self.lbl_status.setText("Status: Ambiente Seguro e Protegido")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            elif score >= 50:
                self.lbl_status.setText("Status: Atenção Requerida (Riscos Moderados)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.lbl_status.setText("Status: Postura Crítica de Segurança")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")

            # Preencher tabela de alertas
            alertas = resultado.get("alertas", [])
            self.tabela_alertas.setRowCount(len(alertas))
            for i, al in enumerate(alertas):
                item_sev = QTableWidgetItem(al["severidade"])
                item_tit = QTableWidgetItem(al["titulo"])
                item_det = QTableWidgetItem(al["detalhe"])
                if al["severidade"] == "Crítico":
                    item_sev.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tabela_alertas.setItem(i, 0, item_sev)
                self.tabela_alertas.setItem(i, 1, item_tit)
                self.tabela_alertas.setItem(i, 2, item_det)

            relatorio = gerar_relatorio_defender(resultado)
            self.txt_relatorio.setPlainText(relatorio)

        def _erro(msg: str) -> None:
            self.btn_auditar.setEnabled(True)
            mostrar_erro(self, "Falha na Auditoria", f"Não foi possível consultar o Defender:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há relatório para salvar.")
            return
        salvar_texto(self, texto, "Salvar Relatório de Auditoria do Defender", "auditoria_defender.txt")

