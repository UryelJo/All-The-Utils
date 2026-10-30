"""Interface gráfica da auditoria do Firewall do Windows (Tool)."""
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
from wintoolbox.tools.system.firewall_audit.logic import (
    coletar_status_firewall,
    gerar_relatorio_firewall,
)


@register
class FirewallAuditTool(Tool):
    """Auditoria defensiva do Firewall do Windows."""

    id = "system.firewall_audit"
    name = "Auditoria do Firewall do Windows"
    category = "Segurança e Análise"
    description = (
        "Audita o estado dos perfis do Firewall do Windows (Domain, Private, Public), "
        "conferindo portas em escuta (LISTEN) e regras permissivas."
    )
    keywords = [
        "firewall",
        "portas",
        "listen",
        "regras",
        "auditoria",
        "rede",
        "segurança",
        "smb",
        "rdp",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FirewallAuditView(self, parent)


class FirewallAuditView(PainelFerramenta):
    """Painel de visualização e auditoria do Firewall."""

    def __init__(self, tool: FirewallAuditTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Ações de Auditoria", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_auditar = QPushButton("Executar Auditoria do Firewall")
        self.btn_auditar.setProperty("accent", True)
        self.btn_auditar.clicked.connect(self._executar_auditoria)
        linha_botoes.addWidget(self.btn_auditar)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Postura
        card_score, lay_score = criar_card("Postura de Firewall e Rede", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Firewall: --")
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

        # Tabela de Portas em Escuta
        card_portas, lay_portas = criar_card("Portas em Escuta (LISTEN)", self)
        self.adicionar(card_portas)

        self.tabela_portas = QTableWidget(0, 5)
        self.tabela_portas.setHorizontalHeaderLabels(["Porta", "Interface", "PID", "Processo", "Classificação"])
        self.tabela_portas.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabela_portas.setAlternatingRowColors(True)
        self.tabela_portas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_portas.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela_portas.setMinimumHeight(140)
        lay_portas.addWidget(self.tabela_portas)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Relatório Técnico do Firewall", self)
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
        self.lbl_score.setText("Score de Firewall: Auditando...")
        self.lbl_status.setText("Examinando perfis de rede e portas abertas...")

        def _tarefa() -> Dict[str, Any]:
            return coletar_status_firewall()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_auditar.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_seguranca"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Firewall: {score}/100")

            if score >= 80:
                self.lbl_status.setText("Status: Perfis Ativos e Protegidos")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            elif score >= 50:
                self.lbl_status.setText("Status: Atenção (Portas Sensíveis Abertas)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.lbl_status.setText("Status: Postura Permissiva (Risco Elevado)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")

            # Preencher tabela de portas
            portas = resultado.get("portas_escuta", [])
            self.tabela_portas.setRowCount(len(portas))
            for i, p in enumerate(portas):
                item_porta = QTableWidgetItem(str(p["porta"]))
                item_ip = QTableWidgetItem(p["ip"])
                item_pid = QTableWidgetItem(str(p["pid"]))
                item_proc = QTableWidgetItem(p["processo"])
                item_class = QTableWidgetItem(p["descricao"] if p["sensivel"] else "Padrão")
                if p["sensivel"]:
                    item_porta.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item_class.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tabela_portas.setItem(i, 0, item_porta)
                self.tabela_portas.setItem(i, 1, item_ip)
                self.tabela_portas.setItem(i, 2, item_pid)
                self.tabela_portas.setItem(i, 3, item_proc)
                self.tabela_portas.setItem(i, 4, item_class)

            relatorio = gerar_relatorio_firewall(resultado)
            self.txt_relatorio.setPlainText(relatorio)

        def _erro(msg: str) -> None:
            self.btn_auditar.setEnabled(True)
            mostrar_erro(self, "Falha na Auditoria", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há relatório para salvar.")
            return
        salvar_texto(self, texto, "Salvar Relatório de Auditoria do Firewall", "auditoria_firewall.txt")

