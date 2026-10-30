"""Gerador e consultor de rainbow tables."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import formatar_bytes, formatar_numero
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    criar_aviso,
    criar_card,
    executar_assincrono,
    mostrar_erro,
)
from wintoolbox.tools.security.rainbow_generator.logic import (
    RainbowProgress,
    consultar_hash,
    estimar_combinacoes,
    estimar_tamanho_bytes,
    gerar_rainbow,
    metadados_tabela,
)
from wintoolbox.ui.widgets.toast import show_toast


@register
class RainbowGeneratorTool(Tool):
    """Geração local de tabelas pré-computadas de hash."""

    id = "security.rainbow_generator"
    name = "Gerador de Rainbow Table"
    category = "Segurança"
    description = (
        "Pré-calcula hashes em um banco SQLite indexado e permite consulta instantânea "
        "de plaintext para MD5, SHA-1 e SHA-256."
    )
    keywords = ["rainbow", "tabela", "pre-computado", "hash", "sqlite"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RainbowGeneratorView(self, parent)


class RainbowGeneratorView(PainelFerramenta):
    """Tela de geração com estimativa e aba de consulta."""

    def __init__(self, tool: RainbowGeneratorTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._executando = False
        self._progresso_atual = 0

        self.tabs = QTabWidget()
        self.adicionar(self.tabs)

        self._montar_geracao()
        self._montar_consulta()
        self._atualizar_estimativa()

    def _montar_geracao(self) -> None:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(10)

        card, form = criar_card("Parâmetros da tabela", aba)
        layout.addWidget(card)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Algoritmo:"))
        self.cmb_algoritmo = QComboBox()
        self.cmb_algoritmo.addItems(["MD5", "SHA-1", "SHA-256"])
        self.cmb_algoritmo.currentTextChanged.connect(self._atualizar_estimativa)
        linha.addWidget(self.cmb_algoritmo)
        linha.addSpacing(20)
        linha.addWidget(QLabel("Charset:"))
        self.txt_charset = QLineEdit("abcdefghijklmnopqrstuvwxyz0123456789")
        self.txt_charset.setFont(QFont("Cascadia Mono, Consolas", 9))
        self.txt_charset.textChanged.connect(self._atualizar_estimativa)
        linha.addWidget(self.txt_charset, stretch=1)
        form.addLayout(linha)

        presets = QHBoxLayout()
        for rotulo, charset in (
            ("a-z", "abcdefghijklmnopqrstuvwxyz"),
            ("A-Z", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            ("0-9", "0123456789"),
            ("a-z 0-9", "abcdefghijklmnopqrstuvwxyz0123456789"),
            ("ASCII completo", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*()-_=+"),
        ):
            botao = QPushButton(rotulo)
            botao.clicked.connect(lambda _=False, c=charset: self.txt_charset.setText(c))
            presets.addWidget(botao)
        presets.addStretch()
        form.addLayout(presets)

        linha2 = QHBoxLayout()
        linha2.addWidget(QLabel("Comprimento mínimo:"))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 8)
        self.spin_min.setValue(1)
        self.spin_min.valueChanged.connect(self._atualizar_estimativa)
        linha2.addWidget(self.spin_min)
        linha2.addWidget(QLabel("máximo:"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, 8)
        self.spin_max.setValue(4)
        self.spin_max.valueChanged.connect(self._atualizar_estimativa)
        linha2.addWidget(self.spin_max)
        linha2.addStretch()
        form.addLayout(linha2)

        linha3 = QHBoxLayout()
        linha3.addWidget(QLabel("Arquivo de saída (.db):"))
        self.txt_saida = QLineEdit()
        self.txt_saida.setPlaceholderText("Escolha onde salvar a rainbow table...")
        linha3.addWidget(self.txt_saida, stretch=1)
        botao_saida = QPushButton("Selecionar...")
        botao_saida.clicked.connect(self._selecionar_saida)
        linha3.addWidget(botao_saida)
        form.addLayout(linha3)

        self.lbl_estimativa = QLabel("")
        self.lbl_estimativa.setWordWrap(True)
        self.lbl_estimativa.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")
        form.addWidget(self.lbl_estimativa)

        self.progresso = QProgressBar()
        self.progresso.setRange(0, 100)
        self.progresso.setValue(0)
        layout.addWidget(self.progresso)

        botoes = QHBoxLayout()
        self.btn_gerar = QPushButton("Gerar Rainbow Table")
        self.btn_gerar.setProperty("accent", True)
        self.btn_gerar.clicked.connect(self._gerar)
        botoes.addWidget(self.btn_gerar)
        self.btn_cancelar = QPushButton("Cancelar e Salvar Parcial")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        botoes.addWidget(self.btn_cancelar)
        botoes.addStretch()
        layout.addLayout(botoes)

        self.lbl_status = QLabel("A geração pode consumir muito disco; confira a estimativa antes de iniciar.")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        layout.addWidget(
            criar_aviso(
                "A rainbow table é um artefato local. Gere apenas para hashes e senhas "
                "sob sua responsabilidade. Tabelas acima de 1 GB exigem confirmação.",
                aba,
            )
        )
        layout.addStretch()
        self.tabs.addTab(aba, "Gerar Tabela")

    def _montar_consulta(self) -> None:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(10)

        card, form = criar_card("Consultar hash", aba)
        layout.addWidget(card)

        linha = QHBoxLayout()
        self.txt_banco = QLineEdit()
        self.txt_banco.setPlaceholderText("Banco .db gerado por esta ferramenta")
        linha.addWidget(self.txt_banco, stretch=1)
        botao_banco = QPushButton("Abrir Banco...")
        botao_banco.clicked.connect(self._selecionar_banco)
        linha.addWidget(botao_banco)
        form.addLayout(linha)

        linha2 = QHBoxLayout()
        self.txt_hash = QLineEdit()
        self.txt_hash.setPlaceholderText("Hash a consultar")
        self.txt_hash.setFont(QFont("Cascadia Mono, Consolas", 10))
        self.txt_hash.returnPressed.connect(self._consultar)
        linha2.addWidget(self.txt_hash, stretch=1)
        self.btn_consultar = QPushButton("Consultar")
        self.btn_consultar.clicked.connect(self._consultar)
        linha2.addWidget(self.btn_consultar)
        form.addLayout(linha2)

        self.lbl_resultado = QLabel("Nenhuma consulta realizada.")
        self.lbl_resultado.setFont(QFont("Segoe UI", 14))
        self.lbl_resultado.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_resultado)

        self.btn_copiar = QPushButton("Copiar Plaintext")
        self.btn_copiar.setEnabled(False)
        self.btn_copiar.clicked.connect(self._copiar_plain)
        layout.addWidget(self.btn_copiar)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setWordWrap(True)
        self.lbl_meta.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_meta)
        layout.addStretch()
        self.tabs.addTab(aba, "Consultar Hash")

    def _selecionar_saida(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar rainbow table", "rainbow.db", "Banco SQLite (*.db);;Todos os arquivos (*.*)"
        )
        if caminho:
            self.txt_saida.setText(caminho)
            self._atualizar_estimativa()

    def _selecionar_banco(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir rainbow table", "", "Banco SQLite (*.db);;Todos os arquivos (*.*)"
        )
        if caminho:
            self.txt_banco.setText(caminho)
            meta = metadados_tabela(Path(caminho))
            if meta:
                self.lbl_meta.setText(
                    "Metadados: " + " | ".join(f"{chave}={valor}" for chave, valor in meta.items())
                )

    def _atualizar_estimativa(self) -> None:
        if not hasattr(self, "txt_charset"):
            return
        charset = self.txt_charset.text()
        minimo = self.spin_min.value()
        maximo = self.spin_max.value()
        combinacoes = estimar_combinacoes(charset, minimo, maximo)
        tamanho = estimar_tamanho_bytes(combinacoes, self.cmb_algoritmo.currentText())
        self.lbl_estimativa.setText(
            f"Combinações: {formatar_numero(combinacoes)} | "
            f"Tamanho estimado do banco: {formatar_bytes(tamanho)}"
        )
        if tamanho > 1024 ** 3:
            self.lbl_estimativa.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")
        else:
            self.lbl_estimativa.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")

    def _gerar(self) -> None:
        if self._executando:
            return
        charset = self.txt_charset.text()
        minimo = self.spin_min.value()
        maximo = self.spin_max.value()
        saida = self.txt_saida.text().strip()
        if len(set(charset)) != len(charset):
            show_toast(self, "Charset duplicado", "Remova caracteres repetidos do charset.", kind="warning")
            return
        if not charset or minimo > maximo:
            show_toast(self, "Parâmetros inválidos", "Revise charset e comprimentos.", kind="warning")
            return
        if not saida:
            show_toast(self, "Destino ausente", "Escolha o arquivo .db de saída.", kind="warning")
            return
        destino = Path(saida)
        if destino.suffix.lower() != ".db":
            destino = destino.with_suffix(".db")

        combinacoes = estimar_combinacoes(charset, minimo, maximo)
        tamanho = estimar_tamanho_bytes(combinacoes, self.cmb_algoritmo.currentText())
        if tamanho > 1024 ** 3:
            resposta = QMessageBox.question(
                self,
                "Tabela muito grande",
                f"A estimativa é de {formatar_bytes(tamanho)} para {formatar_numero(combinacoes)} "
                "combinações. A geração pode demorar e consumir todo o disco livre.\n\nDeseja continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                return
        if destino.exists():
            resposta = QMessageBox.question(
                self,
                "Arquivo existente",
                "O arquivo já existe. As novas entradas serão adicionadas e as duplicadas ignoradas. Continuar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                return

        self._executando = True
        self._progresso_atual = 0
        self.btn_gerar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.progresso.setRange(0, 0)
        self.lbl_status.setText("Gerando tabela...")

        algoritmo = self.cmb_algoritmo.currentText()

        def tarefa(ctx):
            def progresso(gerados: int, total: int) -> None:
                ctx.progress(gerados, total, f"{formatar_numero(gerados)} de {formatar_numero(total)}")

            return gerar_rainbow(
                destino,
                algoritmo,
                charset,
                minimo,
                maximo,
                on_progresso=progresso,
                cancelado=ctx.cancelled,
            )

        def progresso(gerados: int, total: int, mensagem: str) -> None:
            self._progresso_atual = gerados
            if total > 0:
                self.progresso.setRange(0, min(total, 2_000_000_000))
                self.progresso.setValue(min(gerados, 2_000_000_000))
            self.lbl_status.setText(mensagem)

        def concluiu(resultado: RainbowProgress) -> None:
            self._executando = False
            self.btn_gerar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            self.progresso.setValue(100 if not resultado.cancelado else 0)
            self.lbl_status.setText(resultado.resumo())
            self.txt_banco.setText(str(resultado.caminho))
            show_toast(
                self,
                "Rainbow table",
                resultado.resumo(),
                kind="success" if not resultado.cancelado else "info",
                duration_ms=5000,
            )

        def falhou(erro: Exception) -> None:
            self._executando = False
            self.btn_gerar.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            self.lbl_status.setText(f"Falha: {erro}")
            mostrar_erro(self, "Falha na geração", erro)

        executar_assincrono(
            self, tarefa, ao_concluir=concluiu, ao_falhar=falhou, ao_progredir=progresso
        )

    def _cancelar(self) -> None:
        if self.runner.current_worker:
            self.runner.cancel_current()
            self.lbl_status.setText("Cancelamento solicitado; o lote atual será preservado...")

    def _consultar(self) -> None:
        banco = self.txt_banco.text().strip()
        alvo = self.txt_hash.text().strip()
        if not banco or not Path(banco).is_file():
            show_toast(self, "Banco inválido", "Selecione um arquivo .db existente.", kind="warning")
            return
        if not alvo:
            show_toast(self, "Hash ausente", "Informe o hash a consultar.", kind="warning")
            return
        try:
            plain = consultar_hash(Path(banco), alvo)
        except Exception as exc:
            mostrar_erro(self, "Falha na consulta", exc)
            return
        if plain is None:
            self.lbl_resultado.setText("Hash não encontrado nesta tabela.")
            self.btn_copiar.setEnabled(False)
        else:
            self.lbl_resultado.setText(f"Plaintext: {plain}")
            self.btn_copiar.setEnabled(True)
            show_toast(self, "Hash encontrado", plain, kind="success")

    def _copiar_plain(self) -> None:
        texto = self.lbl_resultado.text()
        if texto.startswith("Plaintext: "):
            QApplication.clipboard().setText(texto[len("Plaintext: "):])
            show_toast(self, "Copiado", "Plaintext copiado.", kind="success")
