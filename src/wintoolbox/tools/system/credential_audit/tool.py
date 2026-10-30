"""Interface gráfica da auditoria de credenciais locais (Tool)."""
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
from wintoolbox.tools.system.credential_audit.logic import (
    coletar_credenciais_locais,
    gerar_relatorio_credenciais,
)


@register
class CredentialAuditTool(Tool):
    """Auditoria defensiva de credenciais salvas no Windows."""

    id = "system.credential_audit"
    name = "Auditoria de Credenciais Salvas"
    category = "Segurança e Análise"
    description = (
        "Audita o Gerenciador de Credenciais do Windows (Credential Manager) do perfil local, "
        "analisando complexidade, senhas em branco e reutilização de segredos."
    )
    keywords = [
        "credenciais",
        "credential",
        "senhas",
        "dpapi",
        "auditoria",
        "segurança",
        "higiene",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CredentialAuditView(self, parent)


class CredentialAuditView(PainelFerramenta):
    """Painel de auditoria do Gerenciador de Credenciais."""

    def __init__(self, tool: CredentialAuditTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_acoes, lay_acoes = criar_card("Auditoria do Perfil Atual", self)
        self.adicionar(card_acoes)

        linha_botoes = QHBoxLayout()
        self.btn_auditar = QPushButton("Iniciar Auditoria de Credenciais")
        self.btn_auditar.setProperty("accent", True)
        self.btn_auditar.clicked.connect(self._iniciar_auditoria)
        linha_botoes.addWidget(self.btn_auditar)
        linha_botoes.addStretch()
        lay_acoes.addLayout(linha_botoes)

        # Dashboard de Higiene
        card_score, lay_score = criar_card("Higiene e Postura de Credenciais", self)
        self.adicionar(card_score)

        lay_labels = QHBoxLayout()
        self.lbl_score = QLabel("Score de Higiene: --")
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

        # Tabela de Credenciais
        card_tabela, lay_tabela = criar_card("Credenciais Auditadas (Segredos Ocultados)", self)
        self.adicionar(card_tabela)

        self.tabela_creds = QTableWidget(0, 5)
        self.tabela_creds.setHorizontalHeaderLabels(["Alvo / Serviço", "Usuário", "Tipo", "Força", "Reutilizada"])
        self.tabela_creds.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela_creds.setAlternatingRowColors(True)
        self.tabela_creds.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_creds.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela_creds.setMinimumHeight(150)
        lay_tabela.addWidget(self.tabela_creds)

        # Relatório Completo
        card_rel, lay_rel = criar_card("Relatório Técnico de Credenciais", self)
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

    def _iniciar_auditoria(self) -> None:
        # Aviso ético obrigatório
        resp = QMessageBox.question(
            self,
            "Auditoria de Credenciais",
            "Esta ferramenta lê exclusivamente as credenciais salvas no perfil do usuário atual.\n\n"
            "Deseja iniciar a auditoria defensiva de higiene de senhas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self.btn_auditar.setEnabled(False)
        self.lbl_score.setText("Score de Higiene: Auditando...")
        self.lbl_status.setText("Lendo Credential Manager local...")

        def _tarefa(ctx: Any = None) -> Dict[str, Any]:
            return coletar_credenciais_locais()

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_auditar.setEnabled(True)
            self._resultado = resultado

            score = resultado["score_higiene"]
            self.progresso.setValue(score)
            self.lbl_score.setText(f"Score de Higiene: {score}/100")

            if score >= 80:
                self.lbl_status.setText(f"Status: Bom ({resultado['total_credenciais']} credenciais mapeadas)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #107c41; }")
            elif score >= 50:
                self.lbl_status.setText("Status: Atenção (Senhas Fracas ou Reutilizadas)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #ffb900; }")
            else:
                self.lbl_status.setText("Status: Risco Alto (Senhas Vazias Detectadas)")
                self.progresso.setStyleSheet("QProgressBar::chunk { background-color: #e81123; }")

            # Preencher tabela
            itens = resultado.get("itens", [])
            self.tabela_creds.setRowCount(len(itens))
            for i, it in enumerate(itens):
                item_alvo = QTableWidgetItem(it["alvo"])
                item_user = QTableWidgetItem(it["usuario"])
                item_tipo = QTableWidgetItem(it["tipo"])
                item_forca = QTableWidgetItem(it["forca"])
                item_reuso = QTableWidgetItem("Sim" if it["reutilizada"] else "Não")

                if it["forca"] == "Vazia":
                    item_forca.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                if it["reutilizada"]:
                    item_reuso.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

                self.tabela_creds.setItem(i, 0, item_alvo)
                self.tabela_creds.setItem(i, 1, item_user)
                self.tabela_creds.setItem(i, 2, item_tipo)
                self.tabela_creds.setItem(i, 3, item_forca)
                self.tabela_creds.setItem(i, 4, item_reuso)

            relatorio = gerar_relatorio_credenciais(resultado)
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
        salvar_texto(self, texto, "Salvar Relatório de Auditoria de Credenciais", "auditoria_credenciais.txt")

