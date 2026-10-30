"""Interface gráfica do teste de vazamento de DNS (Tool)."""
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
from wintoolbox.tools.system.dns_leak_test.logic import (
    coletar_dados_dns_leak,
    gerar_relatorio_dns_leak,
)


@register
class DnsLeakTestTool(Tool):
    """Teste de vazamento e privacidade de DNS."""

    id = "system.dns_leak_test"
    name = "Teste de Vazamento de DNS"
    category = "Segurança e Análise"
    description = (
        "Verifica servidores DNS e endereçamento IP para detectar vazamentos de tráfego, "
        "avaliação de conformidade com VPNs e classificação de privacidade."
    )
    keywords = [
        "dns",
        "leak",
        "vazamento",
        "vpn",
        "privacidade",
        "auditoria",
        "segurança",
        "rede",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DnsLeakTestView(self, parent)


class DnsLeakTestView(PainelFerramenta):
    """Painel do teste de vazamento de DNS."""

    def __init__(self, tool: DnsLeakTestTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Ações de Teste de DNS", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_testar = QPushButton("Iniciar Teste de Vazamento de DNS")
        self.btn_testar.setProperty("accent", True)
        self.btn_testar.clicked.connect(self._executar_teste)
        linha_botoes.addWidget(self.btn_testar)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Postura
        card_score, lay_score = criar_card("Postura de Privacidade de DNS", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Privacidade: --")
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

        # Tabela de Servidores DNS
        card_dns, lay_dns = criar_card("Servidores DNS Configurados no Sistema", self)
        self.adicionar(card_dns)

        self.tabela_dns = QTableWidget(0, 3)
        self.tabela_dns.setHorizontalHeaderLabels(["Interface de Rede", "Endereço IP", "Provedor / Classificação"])
        self.tabela_dns.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela_dns.setAlternatingRowColors(True)
        self.tabela_dns.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_dns.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela_dns.setMinimumHeight(130)
        lay_dns.addWidget(self.tabela_dns)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Relatório Técnico de Vazamento", self)
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

    def _executar_teste(self) -> None:
        self.btn_testar.setEnabled(False)
        self.lbl_score.setText("Score de Privacidade: Verificando...")
        self.lbl_status.setText("Consultando resolvers e endpoint de diagnóstico...")

        def _tarefa() -> Dict[str, Any]:
            return coletar_dados_dns_leak()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_testar.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_privacidade"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Privacidade: {score}/100")

            if resultado["possivel_vazamento"]:
                self.lbl_status.setText("Status: Risco de Vazamento Detectado (ISP / Não Protegido)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")
            elif score >= 80:
                self.lbl_status.setText("Status: Seguro (Resolvedores Criptografados / Protegidos)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            else:
                self.lbl_status.setText("Status: Atenção (Configurações Padrão de Rede)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")

            # Preencher tabela
            servidores = resultado.get("servidores_dns", [])
            self.tabela_dns.setRowCount(len(servidores))
            for i, s in enumerate(servidores):
                self.tabela_dns.setItem(i, 0, QTableWidgetItem(s["interface"]))
                self.tabela_dns.setItem(i, 1, QTableWidgetItem(s["ip"]))
                self.tabela_dns.setItem(i, 2, QTableWidgetItem(s["provedor"]))

            relatorio = gerar_relatorio_dns_leak(resultado)
            self.txt_relatorio.setPlainText(relatorio)

        def _erro(msg: str) -> None:
            self.btn_testar.setEnabled(True)
            mostrar_erro(self, "Falha no Teste", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há relatório para salvar.")
            return
        salvar_texto(self, texto, "Salvar Relatório de Teste de DNS", "teste_dns_leak.txt")

