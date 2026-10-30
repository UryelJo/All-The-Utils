"""Interface do quebrador de hashes em CPU e via Hashcat."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
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
    criar_card,
    executar_assincrono,
    mostrar_erro,
)
from wintoolbox.tools.security.hash_cracker.logic import (
    ALGORITMOS_HASHLIB,
    CHARSETS,
    CrackResult,
    HashCracker,
    HashNaoSuportado,
    comando_hashcat,
    detectar_algoritmo,
    encontrar_hashcat,
    quebrar_com_hashcat,
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.tools.security.hash_identify.logic import identify_hash


@register
class HashCrackerTool(Tool):
    """Quebra de hashes com wordlist, força bruta ou Hashcat."""

    id = "security.hash_cracker"
    name = "Quebrador de Hashes (Wordlist e Força Bruta)"
    category = "Segurança"
    description = (
        "Testa senhas contra hashes MD5, SHA, NTLM e outros formatos usando wordlist "
        "ou força bruta, com modo Hashcat opcional."
    )
    keywords = ["cracker", "wordlist", "bruteforce", "hashcat", "john", "senha", "hash"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HashCrackerView(self, parent)


class HashCrackerView(PainelFerramenta):
    """Tela de configuração e acompanhamento da quebra."""

    def __init__(self, tool: HashCrackerTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._executando = False
        self._inicio = 0.0
        self._total_estimado = 0

        self.adicionar_aviso(
            "Esta ferramenta deve ser usada apenas em hashes dos quais você é o proprietário "
            "legítimo ou tem autorização expressa por escrito. Uso contra sistemas de terceiros "
            "é crime previsto na Lei 12.737/2012.",
            destaque=True,
        )

        card, layout = criar_card("Hash alvo", self)
        self.adicionar(card)

        linha = QHBoxLayout()
        self.txt_hash = QLineEdit()
        self.txt_hash.setPlaceholderText("Cole o hash alvo (MD5, SHA-1, SHA-256, NTLM...)")
        self.txt_hash.setFont(QFont("Cascadia Mono, Consolas", 10))
        self.txt_hash.textChanged.connect(self._detectar)
        linha.addWidget(self.txt_hash, stretch=1)

        self.cmb_algoritmo = QComboBox()
        self.cmb_algoritmo.addItems(list(ALGORITMOS_HASHLIB.keys()) + ["NTLM"])
        self.cmb_algoritmo.setMinimumWidth(150)
        self.cmb_algoritmo.currentTextChanged.connect(self._atualizar_modo_hashcat)
        linha.addWidget(self.cmb_algoritmo)
        layout.addLayout(linha)

        self.lbl_deteccao = QLabel("Aguardando o hash para detectar o algoritmo.")
        self.lbl_deteccao.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")
        layout.addWidget(self.lbl_deteccao)

        # Modo de ataque
        self.tabs = QTabWidget()
        self.tab_wordlist = QWidget()
        self.tab_bruto = QWidget()
        self.tabs.addTab(self.tab_wordlist, "Wordlist")
        self.tabs.addTab(self.tab_bruto, "Força Bruta")
        self.adicionar(self.tabs)

        lw = QVBoxLayout(self.tab_wordlist)
        lw.setContentsMargins(8, 10, 8, 10)
        row_w = QHBoxLayout()
        self.chk_wordlist_interna = QRadioButton("Lista interna de 100 senhas comuns")
        self.chk_wordlist_interna.setChecked(True)
        self.chk_wordlist_arquivo = QRadioButton("Arquivo de wordlist:")
        row_w.addWidget(self.chk_wordlist_interna)
        row_w.addWidget(self.chk_wordlist_arquivo)
        self.txt_wordlist = QLineEdit()
        self.txt_wordlist.setPlaceholderText("Caminho da wordlist .txt")
        self.txt_wordlist.setEnabled(False)
        self.btn_wordlist = QPushButton("Selecionar...")
        self.btn_wordlist.setEnabled(False)
        self.btn_wordlist.clicked.connect(self._selecionar_wordlist)
        row_w.addWidget(self.txt_wordlist, stretch=1)
        row_w.addWidget(self.btn_wordlist)
        lw.addLayout(row_w)
        self.chk_wordlist_arquivo.toggled.connect(self._alternar_wordlist)

        lb = QVBoxLayout(self.tab_bruto)
        lb.setContentsMargins(8, 10, 8, 10)
        grid = QGridLayout()
        grid.addWidget(QLabel("Conjuntos de caracteres:"), 0, 0)
        self.checks_charset = {}
        for i, nome in enumerate(CHARSETS):
            check = QCheckBox(nome)
            check.setChecked(nome in {"Minúsculas (a-z)", "Dígitos (0-9)"})
            self.checks_charset[nome] = check
            grid.addWidget(check, 1 + i // 2, i % 2)
        lb.addLayout(grid)

        row_l = QHBoxLayout()
        row_l.addWidget(QLabel("Comprimento mínimo:"))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 12)
        self.spin_min.setValue(1)
        row_l.addWidget(self.spin_min)
        row_l.addWidget(QLabel("Comprimento máximo:"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, 12)
        self.spin_max.setValue(4)
        row_l.addWidget(self.spin_max)
        row_l.addStretch()
        lb.addLayout(row_l)

        # Hashcat opcional
        self.card_hashcat, self.layout_hashcat = criar_card("Aceleração por GPU", self)
        self.adicionar(self.card_hashcat)
        self.chk_hashcat = QCheckBox("Usar Hashcat (GPU) quando disponível")
        self.chk_hashcat.setEnabled(bool(encontrar_hashcat()))
        self.layout_hashcat.addWidget(self.chk_hashcat)
        self.lbl_hashcat = QLabel(
            "Hashcat localizado no PATH." if encontrar_hashcat()
            else "Hashcat não encontrado no PATH. A quebra usará hashlib em CPU."
        )
        self.lbl_hashcat.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 11px;")
        self.layout_hashcat.addWidget(self.lbl_hashcat)

        # Execução
        acoes = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar Quebra")
        self.btn_iniciar.setProperty("accent", True)
        self.btn_iniciar.clicked.connect(self._iniciar)
        acoes.addWidget(self.btn_iniciar)
        self.btn_benchmark = QPushButton("Medir Desempenho")
        self.btn_benchmark.clicked.connect(self._benchmark)
        acoes.addWidget(self.btn_benchmark)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        acoes.addWidget(self.btn_cancelar)
        self.adicionar(QLabel(""))
        self.layout_conteudo.addLayout(acoes)

        self.progresso = QProgressBar()
        self.progresso.setValue(0)
        self.adicionar(self.progresso)

        self.lbl_status = QLabel("Pronto para configurar a quebra.")
        self.lbl_status.setStyleSheet("font-size: 12px;")
        self.adicionar(self.lbl_status)

        self.card_resultado, layout_res = criar_card("Senha encontrada", self)
        self.adicionar(self.card_resultado)
        self.lbl_senha = QLabel("-")
        self.lbl_senha.setFont(QFont("Cascadia Mono, Consolas", 16))
        self.lbl_senha.setStyleSheet("color: #10b981; font-weight: bold;")
        self.lbl_senha.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout_res.addWidget(self.lbl_senha)
        self.btn_copiar_senha = QPushButton("Copiar Senha")
        self.btn_copiar_senha.setEnabled(False)
        self.btn_copiar_senha.clicked.connect(self._copiar_senha)
        layout_res.addWidget(self.btn_copiar_senha)

        self.log = adicionar_log_painel(self, "Log de Tentativas")

    def _alternar_wordlist(self, arquivo: bool) -> None:
        self.txt_wordlist.setEnabled(arquivo)
        self.btn_wordlist.setEnabled(arquivo)
        self.chk_wordlist_interna.setChecked(not arquivo)

    def _selecionar_wordlist(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar wordlist", "", "Listas de senhas (*.txt *.lst *.dic);;Todos os arquivos (*.*)"
        )
        if caminho:
            self.txt_wordlist.setText(caminho)
            self.chk_wordlist_arquivo.setChecked(True)

    def _detectar(self, texto: str) -> None:
        self._atualizar_modo_hashcat()
        if not texto.strip():
            self.lbl_deteccao.setText("Aguardando o hash para detectar o algoritmo.")
            return
        candidatos = identify_hash(texto)
        if not candidatos:
            self.lbl_deteccao.setText("Formato não reconhecido; escolha o algoritmo manualmente.")
            return
        nomes = ", ".join(c.algorithm for c in candidatos[:3])
        melhor = detectar_algoritmo(texto)
        self.cmb_algoritmo.setCurrentText(melhor)
        self.lbl_deteccao.setText(f"Detecção: {nomes}. Algoritmo de trabalho: {melhor}.")

    def _atualizar_modo_hashcat(self) -> None:
        if not hasattr(self, "lbl_hashcat"):
            return
        algoritmo = self.cmb_algoritmo.currentText()
        disponivel = encontrar_hashcat() is not None
        self.chk_hashcat.setEnabled(disponivel and algoritmo in {
            "MD5", "SHA-1", "SHA-224", "SHA-256", "SHA-384", "SHA-512", "NTLM"
        })
        if not disponivel:
            self.lbl_hashcat.setText("Hashcat não encontrado no PATH. A quebra usará hashlib em CPU.")
        elif not self.chk_hashcat.isEnabled():
            self.lbl_hashcat.setText("Hashcat não cobre este formato; será usado o modo nativo em CPU.")
        else:
            self.lbl_hashcat.setText("Hashcat localizado no PATH. O modo GPU está disponível.")

    def _charset_selecionado(self) -> str:
        partes = [CHARSETS[nome] for nome, check in self.checks_charset.items() if check.isChecked()]
        # Remove caracteres repetidos preservando a ordem.
        visto = set()
        saida = []
        for parte in partes:
            for caractere in parte:
                if caractere not in visto:
                    visto.add(caractere)
                    saida.append(caractere)
        return "".join(saida)

    def _iniciar(self) -> None:
        if self._executando:
            return
        if not confirmar_termo_etico(self, self.tool.id):
            return
        hash_alvo = self.txt_hash.text().strip()
        if not hash_alvo:
            show_toast(self, "Hash ausente", "Informe o hash alvo.", kind="warning")
            return

        algoritmo = self.cmb_algoritmo.currentText()
        modo = "forca_bruta" if self.tabs.currentIndex() == 1 else "wordlist"
        wordlist: Optional[Path] = None
        if modo == "wordlist" and self.chk_wordlist_arquivo.isChecked():
            texto = self.txt_wordlist.text().strip()
            if not texto:
                show_toast(self, "Wordlist ausente", "Selecione um arquivo de wordlist.", kind="warning")
                return
            wordlist = Path(texto)
            if not wordlist.is_file():
                show_toast(self, "Wordlist inválida", "O arquivo selecionado não existe.", kind="error")
                return

        charset = self._charset_selecionado()
        minimo = self.spin_min.value()
        maximo = self.spin_max.value()
        if modo == "forca_bruta" and (not charset or minimo > maximo):
            show_toast(self, "Configuração inválida", "Revise charset e comprimentos.", kind="warning")
            return
        if modo == "forca_bruta":
            self._total_estimado = min(
                sum(len(charset) ** n for n in range(minimo, maximo + 1)),
                2_000_000_000,
            )
        else:
            self._total_estimado = 0

        usar_hashcat = (
            self.chk_hashcat.isChecked()
            and self.chk_hashcat.isEnabled()
            and modo == "wordlist"
            and wordlist is not None
            and encontrar_hashcat() is not None
        )

        self._executando = True
        self._inicio = time.perf_counter()
        self.btn_iniciar.setEnabled(False)
        self.btn_benchmark.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.btn_copiar_senha.setEnabled(False)
        self.lbl_senha.setText("-")
        self.log.clear()
        self.progresso.setRange(0, 0 if self._total_estimado == 0 else self._total_estimado)
        self.progresso.setValue(0)
        self.lbl_status.setText("Preparando tentativas...")

        def tarefa(ctx):
            if usar_hashcat and wordlist is not None:
                ctx.log("INFO", "Executando Hashcat em modo wordlist.")
                return quebrar_com_hashcat(hash_alvo, algoritmo, wordlist)

            cracker = HashCracker(hash_alvo, algoritmo, wordlist)
            ctx.log("INFO", f"Algoritmo de trabalho: {cracker.algoritmo}")

            def progresso(tentativas: int, senha: str) -> None:
                total = self._total_estimado or 0
                ctx.progress(tentativas, total, f"{formatar_numero(tentativas)} tentativas | última: {senha[:32]}")

            if modo == "wordlist":
                return cracker.quebrar_wordlist(
                    on_progresso=progresso,
                    cancelado=ctx.cancelled,
                    pausado=ctx.paused,
                )
            return cracker.quebrar_forca_bruta(
                charset=charset,
                comprimento_min=minimo,
                comprimento_max=maximo,
                on_progresso=progresso,
                cancelado=ctx.cancelled,
                pausado=ctx.paused,
            )

        def progresso(tentativas: int, total: int, mensagem: str) -> None:
            if total:
                self.progresso.setRange(0, total)
                self.progresso.setValue(min(tentativas, total))
            decorrido = max(0.001, time.perf_counter() - self._inicio)
            taxa = tentativas / decorrido
            self.lbl_status.setText(
                f"{formatar_numero(tentativas)} tentativa(s) | {formatar_numero(int(taxa))}/s | "
                f"{decorrido:.1f}s"
            )

        def concluiu(resultado: CrackResult) -> None:
            self._executando = False
            self.btn_iniciar.setEnabled(True)
            self.btn_benchmark.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            if resultado.found:
                self.progresso.setValue(100)
                self.lbl_senha.setText(resultado.password or "")
                self.btn_copiar_senha.setEnabled(bool(resultado.password))
                self.lbl_status.setText(resultado.resumo())
                self.log.append_log("INFO", f"Senha encontrada: {resultado.password}")
                show_toast(self, "Senha encontrada", resultado.password or "", kind="success", duration_ms=6000)
            else:
                self.progresso.setValue(0)
                self.lbl_status.setText(resultado.resumo())
                self.log.append_log("WARN", resultado.resumo())
                show_toast(self, "Quebra concluída", resultado.resumo(), kind="info", duration_ms=4000)

        def falhou(erro: Exception) -> None:
            self._executando = False
            self.btn_iniciar.setEnabled(True)
            self.btn_benchmark.setEnabled(True)
            self.btn_cancelar.setEnabled(False)
            self.progresso.setRange(0, 100)
            self.lbl_status.setText(f"Falha: {erro}")
            mostrar_erro(self, "Falha na quebra", erro)

        executar_assincrono(
            self,
            tarefa,
            ao_concluir=concluiu,
            ao_falhar=falhou,
            ao_progredir=progresso,
            ao_logar=lambda nivel, msg: self.log.append_log(nivel, msg),
        )

    def _benchmark(self) -> None:
        algoritmo = self.cmb_algoritmo.currentText()
        if confirmar_termo_etico(self, self.tool.id) is False:
            return
        self.btn_benchmark.setEnabled(False)
        self.lbl_status.setText("Medindo desempenho local...")

        def tarefa(ctx):
            return HashCracker("0" * 32, algoritmo).benchmark(1.2)

        def concluiu(resultado: CrackResult) -> None:
            self.btn_benchmark.setEnabled(True)
            self.lbl_status.setText(
                f"Benchmark {resultado.algorithm}: {formatar_numero(int(resultado.rate))} hashes/s "
                f"em {resultado.elapsed:.2f}s."
            )
            self.log.append_log("INFO", self.lbl_status.text())

        def falhou(erro: Exception) -> None:
            self.btn_benchmark.setEnabled(True)
            mostrar_erro(self, "Benchmark indisponível", erro)

        executar_assincrono(self, tarefa, ao_concluir=concluiu, ao_falhar=falhou)

    def _cancelar(self) -> None:
        if self.runner.current_worker:
            self.runner.cancel_current()
            self.lbl_status.setText("Cancelamento solicitado...")
            self.log.append_log("WARN", "Cancelamento solicitado pelo usuário.")

    def _copiar_senha(self) -> None:
        senha = self.lbl_senha.text().strip()
        if senha and senha != "-":
            QApplication.clipboard().setText(senha)
            show_toast(self, "Senha copiada", "Conteúdo copiado para a área de transferência.", kind="success")
