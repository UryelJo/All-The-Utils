"""Interface do quebrador de segredo HMAC de JWT."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import (
    confirmar_termo_etico,
    formatar_numero,
)
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    criar_aviso,
    criar_card,
    executar_assincrono,
    mostrar_erro,
)
from wintoolbox.tools.security.hash_cracker.logic import CHARSETS
from wintoolbox.tools.security.jwt_secret_cracker.logic import (
    JWTCrackResult,
    JWTInvalido,
    crack_jwt_secret,
    gerar_candidatos_forca_bruta,
    gerar_candidatos_wordlist,
    gerar_jwt,
    parse_jwt,
    resumo_token,
    verificar_assinatura,
)
from wintoolbox.ui.widgets.toast import show_toast


@register
class JWTSecretCrackerTool(Tool):
    """Busca de segredo HMAC de JWT por dicionário ou força bruta."""

    id = "security.jwt_secret_cracker"
    name = "Quebrador de Segredo JWT (HMAC)"
    category = "Segurança"
    description = (
        "Testa segredos HS256, HS384 e HS512 contra um JWT usando wordlist ou força bruta, "
        "com validação de expiração e geração de token de teste."
    )
    keywords = ["jwt", "secret", "hmac", "crack", "hs256", "token"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JWTSecretCrackerView(self, parent)


class JWTSecretCrackerView(PainelFerramenta):
    """Tela de análise, quebra e re-assinatura de JWT."""

    def __init__(self, tool: JWTSecretCrackerTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._info = None
        self._segredo: Optional[str] = None
        self._executando = False

        self.adicionar_aviso(
            "Use somente em tokens próprios ou de sistemas para os quais você possui "
            "autorização escrita. Testar credenciais de terceiros pode violar a Lei 12.737/2012 "
            "e a LGPD.",
            destaque=True,
        )

        card, layout = criar_card("Token JWT", self)
        self.adicionar(card)

        self.txt_token = QPlainTextEdit()
        self.txt_token.setPlaceholderText("Cole o JWT completo (header.payload.assinatura)")
        self.txt_token.setFont(QFont("Cascadia Mono, Consolas", 9))
        self.txt_token.setFixedHeight(92)
        self.txt_token.textChanged.connect(self._agendar_analise)
        layout.addWidget(self.txt_token)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._analisar_token)

        linha = QHBoxLayout()
        self.btn_analisar = QPushButton("Analisar Token")
        self.btn_analisar.clicked.connect(self._analisar_token)
        linha.addWidget(self.btn_analisar)
        self.btn_limpar = QPushButton("Limpar")
        self.btn_limpar.clicked.connect(self._limpar)
        linha.addWidget(self.btn_limpar)
        linha.addStretch()
        layout.addLayout(linha)

        self.info = QTextBrowser()
        self.info.setMinimumHeight(130)
        self.info.setOpenExternalLinks(False)
        self.info.setHtml(
            "<p>Cole um token para visualizar header, payload, expiração e assinatura.</p>"
        )
        self.adicionar(self.info)

        self.tabs = QTabWidget()
        self.adicionar(self.tabs)
        self._montar_wordlist()
        self._montar_bruto()

        acoes = QHBoxLayout()
        self.btn_quebrar = QPushButton("Testar Segredo")
        self.btn_quebrar.setProperty("accent", True)
        self.btn_quebrar.clicked.connect(self._quebrar)
        acoes.addWidget(self.btn_quebrar)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        acoes.addWidget(self.btn_cancelar)
        acoes.addStretch()
        self.layout_conteudo.addLayout(acoes)

        self.progresso = QProgressBar()
        self.progresso.setValue(0)
        self.adicionar(self.progresso)

        self.lbl_status = QLabel("Aguardando token e configuração.")
        self.lbl_status.setStyleSheet("font-size: 12px;")
        self.adicionar(self.lbl_status)

        self.card_resultado, layout_res = criar_card("Segredo encontrado", self)
        self.adicionar(self.card_resultado)
        self.lbl_segredo = QLabel("-")
        self.lbl_segredo.setFont(QFont("Cascadia Mono, Consolas", 15))
        self.lbl_segredo.setStyleSheet("color: #10b981; font-weight: bold;")
        self.lbl_segredo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout_res.addWidget(self.lbl_segredo)

        linha_res = QHBoxLayout()
        self.btn_copiar = QPushButton("Copiar Segredo")
        self.btn_copiar.setEnabled(False)
        self.btn_copiar.clicked.connect(self._copiar_segredo)
        linha_res.addWidget(self.btn_copiar)
        self.btn_reassinar = QPushButton("Gerar Novo JWT com Segredo")
        self.btn_reassinar.setEnabled(False)
        self.btn_reassinar.clicked.connect(self._reassinar)
        linha_res.addWidget(self.btn_reassinar)
        layout_res.addLayout(linha_res)

        self.txt_novo_token = QLineEdit()
        self.txt_novo_token.setReadOnly(True)
        self.txt_novo_token.setPlaceholderText("O token re-assinado aparecerá aqui.")
        self.txt_novo_token.setFont(QFont("Cascadia Mono, Consolas", 8))
        layout_res.addWidget(self.txt_novo_token)
        self.btn_copiar_novo = QPushButton("Copiar Token Re-assinado")
        self.btn_copiar_novo.setEnabled(False)
        self.btn_copiar_novo.clicked.connect(self._copiar_novo)
        layout_res.addWidget(self.btn_copiar_novo)

        self.log = adicionar_log_painel(self, "Log de Tentativas")
        self._agendar_analise()

    def _montar_wordlist(self) -> None:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(8, 10, 8, 10)

        self.chk_arquivo = QCheckBox("Usar arquivo de wordlist")
        layout.addWidget(self.chk_arquivo)
        linha = QHBoxLayout()
        self.txt_wordlist = QLineEdit()
        self.txt_wordlist.setPlaceholderText("Opcional: caminho de uma wordlist .txt")
        self.txt_wordlist.setEnabled(False)
        linha.addWidget(self.txt_wordlist, stretch=1)
        self.btn_wordlist = QPushButton("Selecionar...")
        self.btn_wordlist.setEnabled(False)
        self.btn_wordlist.clicked.connect(self._selecionar_wordlist)
        linha.addWidget(self.btn_wordlist)
        layout.addLayout(linha)
        self.chk_arquivo.toggled.connect(self._alternar_wordlist)

        layout.addWidget(QLabel("Segredos adicionais, um por linha:"))
        self.txt_inline = QPlainTextEdit()
        self.txt_inline.setPlaceholderText("segredo\noutro-segredo\nchave-de-teste")
        self.txt_inline.setFixedHeight(100)
        layout.addWidget(self.txt_inline)
        layout.addWidget(
            criar_aviso(
                "A lista interna de 100 senhas comuns é testada automaticamente. "
                "Ela não inclui segredos específicos da sua aplicação.",
                aba,
            )
        )
        self.tabs.addTab(aba, "Dicionário")

    def _montar_bruto(self) -> None:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(8, 10, 8, 10)

        self.checks_charset = {}
        for nome in CHARSETS:
            check = QCheckBox(nome)
            check.setChecked(nome == "Minúsculas (a-z)")
            self.checks_charset[nome] = check
            layout.addWidget(check)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Comprimento mínimo:"))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 10)
        self.spin_min.setValue(1)
        linha.addWidget(self.spin_min)
        linha.addWidget(QLabel("máximo:"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, 10)
        self.spin_max.setValue(5)
        linha.addWidget(self.spin_max)
        linha.addStretch()
        layout.addLayout(linha)
        layout.addWidget(
            criar_aviso(
                "Força bruta cresce exponencialmente. Para HS512, use comprimentos curtos "
                "e um charset restrito durante o teste.",
                aba,
            )
        )
        self.tabs.addTab(aba, "Força Bruta")

    def _alternar_wordlist(self, ativo: bool) -> None:
        self.txt_wordlist.setEnabled(ativo)
        self.btn_wordlist.setEnabled(ativo)

    def _selecionar_wordlist(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar wordlist", "", "Listas de senhas (*.txt *.lst *.dic);;Todos os arquivos (*.*)"
        )
        if caminho:
            self.txt_wordlist.setText(caminho)
            self.chk_arquivo.setChecked(True)

    def _agendar_analise(self) -> None:
        self._timer.start()

    def _analisar_token(self) -> None:
        texto = self.txt_token.toPlainText().strip()
        if not texto:
            self._info = None
            self.info.setHtml("<p>Cole um token para visualizar header, payload e expiração.</p>")
            return
        try:
            info = parse_jwt(texto)
        except JWTInvalido as exc:
            self._info = None
            self.info.setHtml(f"<p style='color:#ef4444'><b>Token inválido:</b> {exc}</p>")
            return
        self._info = info

        partes_token = texto.split(".")
        cores = ["#60a5fa", "#34d399", "#f59e0b"]
        colorido = ".".join(
            f"<span style='color:{cores[i]}; font-family:Consolas'>{parte[:90]}"
            f"{'...' if len(parte) > 90 else ''}</span>"
            for i, parte in enumerate(partes_token)
        )
        aviso_exp = (
            "<p style='color:#ef4444'><b>Token expirado.</b> A assinatura ainda pode ser válida, "
            "mas o backend deve rejeitá-lo.</p>"
            if info.expirado
            else "<p style='color:#10b981'>Token dentro da validade ou sem claim exp.</p>"
        )
        header_json = json.dumps(info.header, ensure_ascii=False, indent=2)
        payload_json = json.dumps(info.payload, ensure_ascii=False, indent=2)
        self.info.setHtml(
            f"<p><b>Token:</b> {colorido}</p>"
            f"{aviso_exp}"
            f"<p><b>Header</b></p><pre>{self._escapar(header_json)}</pre>"
            f"<p><b>Payload</b></p><pre>{self._escapar(payload_json)}</pre>"
            f"<p>{self._escapar(resumo_token(info))}</p>"
        )

    @staticmethod
    def _escapar(texto: str) -> str:
        return (
            texto.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _charset(self) -> str:
        vistos = set()
        saida = []
        for nome, check in self.checks_charset.items():
            if check.isChecked():
                for caractere in CHARSETS[nome]:
                    if caractere not in vistos:
                        vistos.add(caractere)
                        saida.append(caractere)
        return "".join(saida)

    def _quebrar(self) -> None:
        if self._executando:
            return
        if not confirmar_termo_etico(self, self.tool.id):
            return
        texto = self.txt_token.toPlainText().strip()
        if not texto:
            show_toast(self, "Token ausente", "Cole um JWT antes de testar.", kind="warning")
            return
        try:
            info = parse_jwt(texto)
        except JWTInvalido as exc:
            show_toast(self, "Token inválido", str(exc), kind="error")
            return
        if not info.algorithm.startswith("HS"):
            show_toast(
                self, "Algoritmo não HMAC",
                f"O token usa {info.algorithm or 'algoritmo ausente'}; este ataque se aplica a HS256/384/512.",
                kind="warning",
            )
            return

        modo_bruto = self.tabs.currentIndex() == 1
        charset = self._charset()
        minimo = self.spin_min.value()
        maximo = self.spin_max.value()
        if modo_bruto and (not charset or minimo > maximo):
            show_toast(self, "Configuração inválida", "Revise charset e comprimentos.", kind="warning")
            return

        caminho = Path(self.txt_wordlist.text().strip()) if self.chk_arquivo.isChecked() and self.txt_wordlist.text().strip() else None
        if caminho is not None and not caminho.is_file():
            show_toast(self, "Wordlist inválida", "O arquivo selecionado não existe.", kind="error")
            return
        inline = self.txt_inline.toPlainText()

        self._executando = True
        self._segredo = None
        self.btn_quebrar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_copiar.setEnabled(False)
        self.btn_reassinar.setEnabled(False)
        self.lbl_segredo.setText("-")
        self.txt_novo_token.clear()
        self.btn_copiar_novo.setEnabled(False)
        self.log.clear()
        self.progresso.setRange(0, 0)
        self.lbl_status.setText("Testando segredos...")
        inicio = time.perf_counter()

        def tarefa(ctx):
            if modo_bruto:
                candidatos: Iterable[str] = gerar_candidatos_forca_bruta(charset, minimo, maximo)
            else:
                candidatos = gerar_candidatos_wordlist(caminho, inline)

            def progresso(tentativas: int, candidato: str) -> None:
                ctx.progress(tentativas, 0, f"{formatar_numero(tentativas)} tentativas | {candidato[:40]}")

            return crack_jwt_secret(
                texto,
                candidatos,
                on_progresso=progresso,
                cancelado=ctx.cancelled,
                intervalo=500,
            )

        def progresso(tentativas: int, total: int, mensagem: str) -> None:
            decorrido = max(0.001, time.perf_counter() - inicio)
            self.lbl_status.setText(
                f"{formatar_numero(tentativas)} tentativa(s) | "
                f"{formatar_numero(int(tentativas / decorrido))}/s | {decorrido:.1f}s"
            )

        def concluiu(resultado: JWTCrackResult) -> None:
            self._executando = False
            self.btn_quebrar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            if resultado.found:
                self.progresso.setValue(100)
                self._segredo = resultado.secret
                self.lbl_segredo.setText(resultado.secret or "")
                self.btn_copiar.setEnabled(True)
                self.btn_reassinar.setEnabled(True)
                self.lbl_status.setText(resultado.resumo())
                self.log.append_log("INFO", f"Segredo encontrado: {resultado.secret}")
                show_toast(self, "Segredo encontrado", resultado.secret or "", kind="success", duration_ms=6000)
            else:
                self.progresso.setValue(0)
                self.lbl_status.setText(resultado.resumo())
                self.log.append_log("WARN", resultado.resumo())
                show_toast(self, "Busca concluída", resultado.resumo(), kind="info", duration_ms=4500)

        def falhou(erro: Exception) -> None:
            self._executando = False
            self.btn_quebrar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            self.lbl_status.setText(f"Falha: {erro}")
            mostrar_erro(self, "Falha na busca", erro)

        executar_assincrono(
            self, tarefa, ao_concluir=concluiu, ao_falhar=falhou,
            ao_progredir=progresso, ao_logar=lambda n, m: self.log.append_log(n, m),
        )

    def _cancelar(self) -> None:
        if self.runner.current_worker:
            self.runner.cancel_current()
            self.lbl_status.setText("Cancelamento solicitado...")

    def _copiar_segredo(self) -> None:
        if self._segredo:
            QApplication.clipboard().setText(self._segredo)
            show_toast(self, "Copiado", "Segredo copiado.", kind="success")

    def _reassinar(self) -> None:
        if not self._segredo or self._info is None:
            return
        try:
            novo = gerar_jwt(self._info.payload, self._segredo, self._info.algorithm)
        except Exception as exc:
            mostrar_erro(self, "Falha ao re-assinar", exc)
            return
        self.txt_novo_token.setText(novo)
        self.btn_copiar_novo.setEnabled(True)
        if verificar_assinatura(novo, self._segredo):
            show_toast(self, "Token re-assinado", "Assinatura validada com o segredo encontrado.", kind="success")
        else:
            show_toast(self, "Falha de validação", "O token gerado não validou.", kind="error")

    def _copiar_novo(self) -> None:
        if self.txt_novo_token.text():
            QApplication.clipboard().setText(self.txt_novo_token.text())
            show_toast(self, "Copiado", "Token re-assinado copiado.", kind="success")

    def _limpar(self) -> None:
        self.txt_token.clear()
        self._info = None
        self._segredo = None
        self.info.clear()
        self.lbl_segredo.setText("-")
        self.txt_novo_token.clear()
        self.btn_copiar.setEnabled(False)
        self.btn_reassinar.setEnabled(False)
        self.btn_copiar_novo.setEnabled(False)
