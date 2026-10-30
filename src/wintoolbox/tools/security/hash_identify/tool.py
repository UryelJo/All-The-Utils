"""Identificador de tipo de hash por assinatura e comprimento."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import formatar_numero
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    botao_copiar,
    criar_aviso,
    criar_card,
    preencher_tabela,
)
from wintoolbox.tools.security.hash_identify.logic import HashCandidate, hashcat_command, identify_hash
from wintoolbox.ui.widgets.toast import show_toast


@register
class HashIdentifierTool(Tool):
    """Ferramenta de identificação de algoritmos de hash."""

    id = "security.hash_identify"
    name = "Identificador de Tipo de Hash"
    category = "Segurança"
    description = (
        "Detecta o algoritmo provável de um hash por análise de formato, "
        "comprimento, prefixo e codificação."
    )
    keywords = ["hash", "md5", "sha", "bcrypt", "argon2", "identificar", "forense"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HashIdentifierView(self, parent)


class HashIdentifierView(PainelFerramenta):
    """Tela de análise com atualização em tempo real e detalhamento."""

    def __init__(self, tool: HashIdentifierTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)

        self._ultimo_texto = ""
        self._candidatos: List[HashCandidate] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._analisar)

        card, layout = criar_card("Hash para analisar", self)
        self.adicionar(card)

        linha = QHBoxLayout()
        self.txt_hash = QLineEdit()
        self.txt_hash.setPlaceholderText(
            "Cole o hash com ou sem prefixo, por exemplo $2b$, pbkdf2_sha256$ ou *AABB..."
        )
        self.txt_hash.setFont(QFont("Cascadia Mono, Consolas", 10))
        self.txt_hash.textChanged.connect(self._ao_digitar)
        self.txt_hash.returnPressed.connect(self._analisar)
        linha.addWidget(self.txt_hash, stretch=1)

        self.btn_analisar = QPushButton("Analisar")
        self.btn_analisar.setProperty("accent", True)
        self.btn_analisar.clicked.connect(self._analisar)
        linha.addWidget(self.btn_analisar)
        layout.addLayout(linha)

        self.lbl_status = QLabel("A análise começa automaticamente após 300 ms de pausa na digitação.")
        self.lbl_status.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_status)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(
            ["Algoritmo", "Confiança", "Modo Hashcat", "Comprimento", "Motivo", "Exemplo"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setMinimumHeight(230)
        self.tabela.itemSelectionChanged.connect(self._mostrar_detalhe)
        self.adicionar(self.tabela, esticar=1)

        self.detalhe = QTextBrowser()
        self.detalhe.setOpenExternalLinks(False)
        self.detalhe.setMinimumHeight(115)
        self.detalhe.setPlaceholderText("Selecione um candidato para ver detalhes e o comando Hashcat.")
        self.adicionar(self.detalhe)

        acoes = QHBoxLayout()
        self.btn_copiar = QPushButton("Copiar Resultado")
        self.btn_copiar.clicked.connect(self._copiar_resultado)
        acoes.addWidget(self.btn_copiar)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self._limpar)
        acoes.addWidget(self.btn_limpar)
        acoes.addStretch()
        self.adicionar(QLabel(""))
        self.layout_conteudo.addLayout(acoes)

        self.adicionar(
            criar_aviso(
                "Se nenhum candidato corresponder, o hash pode estar truncado, usar salt "
                "customizado, estar em formato proprietário ou não ser um hash."
            )
        )

    def _ao_digitar(self, texto: str) -> None:
        self._timer.start()
        if not texto.strip():
            self._limpar(manter_texto=True)

    def _analisar(self) -> None:
        texto = self.txt_hash.text().strip()
        self._ultimo_texto = texto
        if not texto:
            self._limpar(manter_texto=True)
            self.lbl_status.setText("Informe um hash para iniciar a análise.")
            return

        try:
            self._candidatos = identify_hash(texto)
        except Exception as exc:  # pragma: no cover - proteção de UI
            show_toast(self, "Falha na análise", str(exc), kind="error")
            return

        linhas = []
        for candidato in self._candidatos:
            modo = f"-m {candidato.hashcat_mode}" if candidato.hashcat_mode is not None else "Nativo em CPU"
            linhas.append(
                [
                    candidato.algorithm,
                    candidato.confidence,
                    modo,
                    candidato.expected_length or len(texto),
                    candidato.reason,
                    candidato.example,
                ]
            )
        preencher_tabela(self.tabela, linhas)
        self.tabela.resizeColumnsToContents()
        self.tabela.setColumnWidth(4, 320)

        if self._candidatos:
            self.lbl_status.setText(
                f"{formatar_numero(len(self._candidatos))} candidato(s) encontrado(s) para "
                f"{len(texto)} caractere(s). Clique em uma linha para ver o comando Hashcat."
            )
            self.tabela.selectRow(0)
            self._mostrar_detalhe()
        else:
            self.lbl_status.setText("Nenhum formato conhecido corresponde a esta string.")
            self.detalhe.clear()

    def _candidato_selecionado(self) -> Optional[HashCandidate]:
        linhas = self.tabela.selectionModel().selectedRows() if self.tabela.selectionModel() else []
        if linhas:
            indice = linhas[0].row()
            if 0 <= indice < len(self._candidatos):
                return self._candidatos[indice]
        return None

    def _mostrar_detalhe(self) -> None:
        candidato = self._candidato_selecionado()
        if candidato is None:
            return
        comando = hashcat_command(candidato, self._ultimo_texto)
        confianca_cor = {"Alto": "#10b981", "Médio": "#f59e0b", "Baixa": "#ef4444"}.get(
            candidato.confidence, "#9ca3af"
        )
        self.detalhe.setHtml(
            f"<p><b>{candidato.algorithm}</b> "
            f"<span style='color:{confianca_cor}'>Confiança {candidato.confidence}</span></p>"
            f"<p>{candidato.reason}</p>"
            f"<p><b>Exemplo:</b> <code>{candidato.example}</code></p>"
            f"<p><b>Hashcat:</b> <code>{comando}</code></p>"
        )

    def _copiar_resultado(self) -> None:
        if not self._candidatos:
            show_toast(self, "Nada para copiar", "Nenhum candidato identificado.", kind="warning")
            return
        partes = [f"Hash analisado: {self._ultimo_texto}", ""]
        for candidato in self._candidatos:
            partes.append(
                f"{candidato.algorithm} | Confiança: {candidato.confidence} | "
                f"Modo: {candidato.hashcat_mode if candidato.hashcat_mode is not None else 'nativo'} | "
                f"{candidato.reason}"
            )
        QApplication.clipboard().setText("\n".join(partes))
        show_toast(self, "Resultado copiado", "Candidatos copiados.", kind="success")

    def _limpar(self, manter_texto: bool = False) -> None:
        self._candidatos = []
        self.tabela.setRowCount(0)
        self.detalhe.clear()
        if not manter_texto:
            self.txt_hash.clear()
        self.lbl_status.setText("A análise começa automaticamente após 300 ms de pausa na digitação.")
