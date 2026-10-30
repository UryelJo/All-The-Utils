"""Ferramenta de ataques matemáticos a RSA fraco (Tool).

Implementa ataques criptoanalíticos para recuperação de chaves privadas e mensagens
cifradas em implementações vulneráveis de RSA:
1. Ataque de Wiener para expoente privado d pequeno (d < (1/3) * N^0.25);
2. Fatoração de Fermat para primos muito próximos (p ≈ q);
3. Ataque do Módulo Comum (mesmo N com múltiplos expoentes coprimos);
4. Hastad Broadcast Attack via Teorema Chinês dos Restos (CRT) para expoente pequeno.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
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
from wintoolbox.tools.crypto.rsa_logic import (
    analise_automatica,
    ataque_hastad,
    ataque_modulo_comum,
    ataque_wiener,
    fatorar_fermat,
    parse_chaves_hastad,
    parse_inteiro,
    relatorio_analise_automatica,
    relatorio_fermat,
    relatorio_hastad,
    relatorio_modulo_comum,
    relatorio_wiener,
)


@register
class RsaAttackTool(Tool):
    """Criptoanálise e ataques a RSA fraco."""

    id = "crypto.rsa_attack"
    name = "Ataques a RSA Fraco"
    category = "Segurança e Análise"
    description = (
        "Ferramenta de criptoanálise de chaves e cifras RSA fracas (Wiener, Fermat, "
        "Módulo Comum e Hastad Broadcast) para testes de segurança e desafios CTF."
    )
    keywords = [
        "rsa",
        "wiener",
        "fermat",
        "módulo comum",
        "hastad",
        "crt",
        "fatoração",
        "criptoanálise",
        "ctf",
        "chave privada",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RsaAttackView(self, parent)


class RsaAttackView(PainelFerramenta):
    """Painel de criptoanálise RSA com abas por modalidade de ataque."""

    def __init__(self, tool: RsaAttackTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._build_ui()

    def _build_ui(self) -> None:
        card_ataques, lay_ataques = criar_card("Modalidades de Ataque RSA", self)
        self.adicionar(card_ataques)

        self.tabs = QTabWidget()
        lay_ataques.addWidget(self.tabs)

        # Aba 1: Análise Automática / Wiener
        tab_wiener = QWidget()
        lay_w = QVBoxLayout(tab_wiener)
        form_w = QFormLayout()

        self.txt_w_n = QLineEdit()
        self.txt_w_n.setPlaceholderText("Módulo N (decimal ou 0xhex)")
        form_w.addRow("Módulo N:", self.txt_w_n)

        self.txt_w_e = QLineEdit()
        self.txt_w_e.setText("65537")
        self.txt_w_e.setPlaceholderText("Expoente público e (ex: 65537, 3, etc.)")
        form_w.addRow("Expoente e:", self.txt_w_e)

        self.txt_w_c = QLineEdit()
        self.txt_w_c.setPlaceholderText("Opcional: Ciphertext c para decifrar a mensagem")
        form_w.addRow("Ciphertext c:", self.txt_w_c)
        lay_w.addLayout(form_w)

        btn_run_wiener = QPushButton("Executar Análise Automática / Wiener")
        btn_run_wiener.setProperty("accent", True)
        btn_run_wiener.clicked.connect(self._executar_wiener)
        lay_w.addWidget(btn_run_wiener)
        self.tabs.addTab(tab_wiener, "Wiener / Automático")

        # Aba 2: Fermat
        tab_fermat = QWidget()
        lay_f = QVBoxLayout(tab_fermat)
        form_f = QFormLayout()

        self.txt_f_n = QLineEdit()
        self.txt_f_n.setPlaceholderText("Módulo N (decimal ou 0xhex)")
        form_f.addRow("Módulo N:", self.txt_f_n)

        self.txt_f_e = QLineEdit()
        self.txt_f_e.setText("65537")
        form_f.addRow("Expoente e:", self.txt_f_e)

        self.txt_f_c = QLineEdit()
        self.txt_f_c.setPlaceholderText("Opcional: Ciphertext c")
        form_f.addRow("Ciphertext c:", self.txt_f_c)

        self.spn_f_iter = QSpinBox()
        self.spn_f_iter.setRange(10_000, 20_000_000)
        self.spn_f_iter.setSingleStep(100_000)
        self.spn_f_iter.setValue(2_000_000)
        form_f.addRow("Limite de Iterações:", self.spn_f_iter)
        lay_f.addLayout(form_f)

        btn_run_fermat = QPushButton("Executar Fatoração de Fermat (p ≈ q)")
        btn_run_fermat.setProperty("accent", True)
        btn_run_fermat.clicked.connect(self._executar_fermat)
        lay_f.addWidget(btn_run_fermat)
        self.tabs.addTab(tab_fermat, "Fermat (p ≈ q)")

        # Aba 3: Módulo Comum
        tab_mc = QWidget()
        lay_mc = QVBoxLayout(tab_mc)
        form_mc = QFormLayout()

        self.txt_mc_n = QLineEdit()
        self.txt_mc_n.setPlaceholderText("Módulo N compartilhado")
        form_mc.addRow("Módulo N:", self.txt_mc_n)

        self.txt_mc_e1 = QLineEdit()
        form_mc.addRow("Expoente e1:", self.txt_mc_e1)

        self.txt_mc_c1 = QLineEdit()
        form_mc.addRow("Ciphertext c1:", self.txt_mc_c1)

        self.txt_mc_e2 = QLineEdit()
        form_mc.addRow("Expoente e2:", self.txt_mc_e2)

        self.txt_mc_c2 = QLineEdit()
        form_mc.addRow("Ciphertext c2:", self.txt_mc_c2)
        lay_mc.addLayout(form_mc)

        btn_run_mc = QPushButton("Executar Ataque do Módulo Comum")
        btn_run_mc.setProperty("accent", True)
        btn_run_mc.clicked.connect(self._executar_modulo_comum)
        lay_mc.addWidget(btn_run_mc)
        self.tabs.addTab(tab_mc, "Módulo Comum")

        # Aba 4: Hastad Broadcast
        tab_h = QWidget()
        lay_h = QVBoxLayout(tab_h)
        lbl_h_info = QLabel("Insira as chaves e cifras no formato:\nN1, e1, c1\nN2, e2, c2\nN3, e3, c3")
        lbl_h_info.setStyleSheet("color: rgba(255,255,255,0.7);")
        lay_h.addWidget(lbl_h_info)

        self.txt_h_dados = QPlainTextEdit()
        self.txt_h_dados.setPlaceholderText("N1, e, c1\nN2, e, c2\nN3, e, c3...")
        self.txt_h_dados.setMaximumHeight(110)
        lay_h.addWidget(self.txt_h_dados)

        btn_run_hastad = QPushButton("Executar Hastad Broadcast (CRT)")
        btn_run_hastad.setProperty("accent", True)
        btn_run_hastad.clicked.connect(self._executar_hastad)
        lay_h.addWidget(btn_run_hastad)
        self.tabs.addTab(tab_h, "Hastad Broadcast")

        # Resultado / Relatório
        card_res, lay_res = criar_card("Relatório de Criptoanálise", self)
        self.adicionar(card_res, esticar=1)

        self.txt_resultado = criar_saida_texto(card_res)
        lay_res.addWidget(self.txt_resultado, stretch=1)

        linha_acoes = QHBoxLayout()
        self.btn_copiar = botao_copiar(self.txt_resultado, "Copiar Relatório", card_res)
        linha_acoes.addWidget(self.btn_copiar)

        self.btn_salvar = QPushButton("Salvar Relatório (.txt)")
        self.btn_salvar.clicked.connect(self._salvar_relatorio)
        linha_acoes.addWidget(self.btn_salvar)
        linha_acoes.addStretch()
        lay_res.addLayout(linha_acoes)

    def _executar_wiener(self) -> None:
        try:
            n = parse_inteiro(self.txt_w_n.text())
            e = parse_inteiro(self.txt_w_e.text())
            c_str = self.txt_w_c.text().strip()
            c = parse_inteiro(c_str) if c_str else None
        except ValueError as exc:
            mostrar_erro(self, "Entrada Inválida", str(exc))
            return

        self.txt_resultado.setPlainText("Executando ataque de Wiener e análise automática de vulnerabilidades...")

        def _tarefa(ctx: Any = None) -> str:
            res = analise_automatica(n, e, c)
            return relatorio_analise_automatica(res, c)

        def _sucesso(rel: str) -> None:
            self.txt_resultado.setPlainText(rel)

        def _erro(msg: str) -> None:
            mostrar_erro(self, "Falha no Ataque", f"Erro durante a execução:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _executar_fermat(self) -> None:
        try:
            n = parse_inteiro(self.txt_f_n.text())
            e_str = self.txt_f_e.text().strip()
            e = parse_inteiro(e_str) if e_str else 65537
            c_str = self.txt_f_c.text().strip()
            c = parse_inteiro(c_str) if c_str else None
            max_iter = self.spn_f_iter.value()
        except ValueError as exc:
            mostrar_erro(self, "Entrada Inválida", str(exc))
            return

        self.txt_resultado.setPlainText(f"Executando fatoração de Fermat com até {max_iter:,} iterações...")

        def _tarefa(ctx: Any = None) -> str:
            res = fatorar_fermat(n, max_iteracoes=max_iter)
            return relatorio_fermat(res, n, e=e, cifra=c)

        def _sucesso(rel: str) -> None:
            self.txt_resultado.setPlainText(rel)

        def _erro(msg: str) -> None:
            mostrar_erro(self, "Falha na Fatoração", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _executar_modulo_comum(self) -> None:
        try:
            n = parse_inteiro(self.txt_mc_n.text())
            e1 = parse_inteiro(self.txt_mc_e1.text())
            c1 = parse_inteiro(self.txt_mc_c1.text())
            e2 = parse_inteiro(self.txt_mc_e2.text())
            c2 = parse_inteiro(self.txt_mc_c2.text())
        except ValueError as exc:
            mostrar_erro(self, "Entrada Inválida", str(exc))
            return

        self.txt_resultado.setPlainText("Executando ataque do Módulo Comum via Algoritmo Estendido de Euclides...")

        def _tarefa(ctx: Any = None) -> str:
            res = ataque_modulo_comum(n, e1, c1, e2, c2)
            return relatorio_modulo_comum(res)

        def _sucesso(rel: str) -> None:
            self.txt_resultado.setPlainText(rel)

        def _erro(msg: str) -> None:
            mostrar_erro(self, "Falha no Ataque", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _executar_hastad(self) -> None:
        texto = self.txt_h_dados.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Entrada Vazia", "Insira a lista de chaves e cifras.")
            return

        try:
            chaves = parse_chaves_hastad(texto)
        except ValueError as exc:
            mostrar_erro(self, "Formato Inválido", str(exc))
            return

        self.txt_resultado.setPlainText("Executando ataque Hastad Broadcast via Teorema Chinês dos Restos (CRT)...")

        def _tarefa(ctx: Any = None) -> str:
            res = ataque_hastad(chaves)
            return relatorio_hastad(res, chaves)

        def _sucesso(rel: str) -> None:
            self.txt_resultado.setPlainText(rel)

        def _erro(msg: str) -> None:
            mostrar_erro(self, "Falha no Ataque", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_resultado.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há relatório para salvar.")
            return
        salvar_texto(self, texto, "Salvar Relatório de Ataque RSA", "relatorio_rsa.txt")
