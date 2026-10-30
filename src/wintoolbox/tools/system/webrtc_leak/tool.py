"""Interface gráfica do detector de vazamento WebRTC (Tool)."""
from __future__ import annotations

import webbrowser
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
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
    mostrar_erro,
)
from wintoolbox.tools.system.webrtc_leak.logic import (
    analisar_candidatos_webrtc,
    gerar_relatorio_webrtc,
    iniciar_servidor_diagnostico,
)


@register
class WebrtcLeakTool(Tool):
    """Detector de vazamento de IP via WebRTC."""

    id = "system.webrtc_leak"
    name = "Detector de Vazamento WebRTC"
    category = "Segurança e Análise"
    description = (
        "Diagnostica vazamento de endereços IP locais e públicos expostos através de "
        "candidatos ICE WebRTC em navegadores e conexões VPN."
    )
    keywords = [
        "webrtc",
        "leak",
        "vazamento",
        "vpn",
        "ip",
        "privacidade",
        "segurança",
        "auditoria",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WebrtcLeakView(self, parent)


class WebrtcLeakView(PainelFerramenta):
    """Painel de teste e diagnóstico de WebRTC Leak."""

    def __init__(self, tool: WebrtcLeakTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._servidor_cleanup: Optional[Any] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Diagnóstico no Navegador", self)
        self.adicionar(card_acoes)

        lbl_desc = QLabel(
            "O WebRTC executa no contexto do seu navegador web padrão. Ao clicar no botão abaixo, "
            "uma página de diagnóstico local segura será aberta para colher os candidatos ICE gerados."
        )
        lbl_desc.setStyleSheet("color: rgba(255,255,255,0.7);")
        lbl_desc.setWordWrap(True)
        lay_acoes.addWidget(lbl_desc)

        linha_botoes = QHBoxLayout()
        self.btn_iniciar = QPushButton("Abrir Teste no Navegador")
        self.btn_iniciar.setProperty("accent", True)
        self.btn_iniciar.clicked.connect(self._iniciar_teste_webrtc)
        linha_botoes.addWidget(self.btn_iniciar)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Postura
        card_score, lay_score = criar_card("Postura de Privacidade WebRTC", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Privacidade: --")
        self.lbl_score.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lay_labels.addWidget(self.lbl_score)

        self.lbl_status = QLabel("Status: Aguardando execução do teste")
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        lay_labels.addWidget(self.lbl_status)
        lay_labels.addStretch()
        lay_score.addLayout(lay_labels)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        self.progresso.setFormat("%v / 100")
        lay_score.addWidget(self.progresso)

        # Tabela de IPs Expostos
        card_ips, lay_ips = criar_card("Endereços IP Detectados via WebRTC", self)
        self.adicionar(card_ips)

        self.tabela_ips = QTableWidget(0, 2)
        self.tabela_ips.setHorizontalHeaderLabels(["Endereço IP", "Tipo / Classificação"])
        self.tabela_ips.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela_ips.setAlternatingRowColors(True)
        self.tabela_ips.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_ips.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela_ips.setMinimumHeight(110)
        lay_ips.addWidget(self.tabela_ips)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Relatório Técnico de WebRTC", self)
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

    def _iniciar_teste_webrtc(self) -> None:
        if self._servidor_cleanup:
            self._servidor_cleanup()
            self._servidor_cleanup = None

        self.btn_iniciar.setEnabled(False)
        self.lbl_score.setText("Score de Privacidade: Aguardando resposta do navegador...")
        self.lbl_status.setText("Aguardando candidatos ICE...")

        def _recebido(ips: List[str]) -> None:
            # Invocar na thread principal Qt
            QTimer.singleShot(0, lambda: self._processar_ips_recebidos(ips))

        try:
            url, server, cleanup = iniciar_servidor_diagnostico(_recebido)
            self._servidor_cleanup = cleanup
            webbrowser.open(url)
        except Exception as exc:
            self.btn_iniciar.setEnabled(True)
            mostrar_erro(self, "Falha ao Iniciar Servidor Local", str(exc))

    def _processar_ips_recebidos(self, ips: List[str]) -> None:
        self.btn_iniciar.setEnabled(True)
        if self._servidor_cleanup:
            self._servidor_cleanup()
            self._servidor_cleanup = None

        resultado = analisar_candidatos_webrtc(ips)
        score = resultado["score_privacidade"]
        self.progresso.setValue(score)
        self.lbl_score.setText(f"Score de Privacidade: {score}/100")

        if resultado["vazamento_detectado"]:
            self.lbl_status.setText("Status: Vazamento Crítico de IP Detectado!")
            self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")
        elif score >= 80:
            self.lbl_status.setText("Status: Seguro (WebRTC Protegido ou Sem Vazamento)")
            self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
        else:
            self.lbl_status.setText("Status: Atenção (IPs de Rede Local Expostos)")
            self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")

        # Preencher tabela de IPs
        todas_linhas: List[Tuple[str, str]] = []
        for ip in resultado["ips_privados"]:
            todas_linhas.append((ip, "IP Privado (Rede Local)"))
        for ip in resultado["ips_publicos"]:
            todas_linhas.append((ip, "IP Público Exposto"))

        self.tabela_ips.setRowCount(len(todas_linhas))
        for i, (ip, tipo) in enumerate(todas_linhas):
            self.tabela_ips.setItem(i, 0, QTableWidgetItem(ip))
            self.tabela_ips.setItem(i, 1, QTableWidgetItem(tipo))

        relatorio = gerar_relatorio_webrtc(resultado)
        self.txt_relatorio.setPlainText(relatorio)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há laudo para salvar.")
            return
        salvar_texto(self, texto, "Salvar Laudo de WebRTC Leak", "laudo_webrtc_leak.txt")

