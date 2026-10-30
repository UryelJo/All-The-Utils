"""Criptoanálise e quebra automatizada de cifras clássicas (Tool).

Quebra e analisa cifras históricas por frequência de n-gramas e testes estatísticos:
1. Análise de Frequência de caracteres e Índice de Coincidência (IC de Friedman);
2. Quebra exaustiva da Cifra de César com pontuação léxica em Português;
3. Criptoanálise da Cifra de Vigenère via Exame de Kasiski e determinação de chave;
4. Quebra heurística de Cifra de Substituição Monoalfabética por busca estocástica.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
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
from wintoolbox.tools.crypto.classical_logic import (
    analisar_texto,
    gerar_relatorio,
    quebrar_cesar,
    quebrar_substituicao,
    quebrar_vigenere,
)


@register
class ClassicalBreakTool(Tool):
    """Criptoanálise de cifras clássicas (César, Vigenère e Substituição)."""

    id = "crypto.classical_break"
    name = "Criptoanálise de Cifras Clássicas"
    category = "Segurança e Análise"
    description = (
        "Identifica e quebra cifras clássicas (César, Vigenère e Substituição) "
        "através de frequência de n-gramas em português, Índice de Coincidência e teste de Kasiski."
    )
    keywords = [
        "cifra",
        "césar",
        "cesar",
        "vigenère",
        "vigenere",
        "kasiski",
        "substituição",
        "criptoanálise",
        "frequência",
        "ctf",
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ClassicalBreakView(self, parent)


class ClassicalBreakView(PainelFerramenta):
    """Interface de quebra de cifras clássicas com abas por algoritmo e relatório unificado."""

    def __init__(self, tool: ClassicalBreakTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        card_entrada, lay_entrada = criar_card("Texto Cifrado", self)
        self.adicionar(card_entrada)

        self.txt_cifrado = QPlainTextEdit()
        self.txt_cifrado.setPlaceholderText("Cole aqui o texto cifrado para quebrar...")
        self.txt_cifrado.setFont(QFont("Cascadia Mono, Consolas", 10))
        self.txt_cifrado.setMaximumHeight(100)
        lay_entrada.addWidget(self.txt_cifrado)

        linha_botoes = QHBoxLayout()
        linha_botoes.addWidget(QLabel("Tamanho máximo de chave (Vigenère):"))
        self.spn_chave_max = QSpinBox()
        self.spn_chave_max.setRange(2, 40)
        self.spn_chave_max.setValue(15)
        linha_botoes.addWidget(self.spn_chave_max)

        self.btn_analisar_tudo = QPushButton("Análise Completa (Todas as Cifras)")
        self.btn_analisar_tudo.setProperty("accent", True)
        self.btn_analisar_tudo.clicked.connect(self._quebrar_todas)
        linha_botoes.addWidget(self.btn_analisar_tudo)
        linha_botoes.addStretch()
        lay_entrada.addLayout(linha_botoes)

        # Abas de Resultados
        card_res, lay_res = criar_card("Diagnóstico e Textos Decifrados", self)
        self.adicionar(card_res, esticar=1)

        self.tabs = QTabWidget()
        lay_res.addWidget(self.tabs, stretch=1)

        # Aba 1: Relatório Consolidado
        tab_rel = QWidget()
        lay_rel = QVBoxLayout(tab_rel)
        self.txt_relatorio = criar_saida_texto(tab_rel)
        lay_rel.addWidget(self.txt_relatorio)
        self.tabs.addTab(tab_rel, "Relatório Completo")

        # Aba 2: César
        tab_cesar = QWidget()
        lay_cesar = QVBoxLayout(tab_cesar)
        self.lbl_cesar_resumo = QLabel("Aguardando análise...")
        self.lbl_cesar_resumo.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lay_cesar.addWidget(self.lbl_cesar_resumo)

        self.tabela_cesar = QTableWidget(0, 3)
        self.tabela_cesar.setHorizontalHeaderLabels(["Deslocamento", "Pontuação", "Texto Decifrado (Amostra)"])
        self.tabela_cesar.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela_cesar.setAlternatingRowColors(True)
        self.tabela_cesar.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela_cesar.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay_cesar.addWidget(self.tabela_cesar)
        self.tabs.addTab(tab_cesar, "Cifra de César")

        # Aba 3: Vigenère
        tab_vig = QWidget()
        lay_vig = QVBoxLayout(tab_vig)
        self.lbl_vig_chave = QLabel("Chave Provável: --")
        self.lbl_vig_chave.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lay_vig.addWidget(self.lbl_vig_chave)

        self.txt_vig_decifrado = criar_saida_texto(tab_vig)
        lay_vig.addWidget(self.txt_vig_decifrado)
        self.tabs.addTab(tab_vig, "Cifra de Vigenère")

        # Aba 4: Substituição
        tab_sub = QWidget()
        lay_sub = QVBoxLayout(tab_sub)
        self.lbl_sub_info = QLabel("Mapeamento do Alfabeto: --")
        lay_sub.addWidget(self.lbl_sub_info)

        self.txt_sub_decifrado = criar_saida_texto(tab_sub)
        lay_sub.addWidget(self.txt_sub_decifrado)
        self.tabs.addTab(tab_sub, "Substituição Simples")

        linha_acoes = QHBoxLayout()
        self.btn_copiar = botao_copiar(self.txt_relatorio, "Copiar Relatório", card_res)
        linha_acoes.addWidget(self.btn_copiar)

        self.btn_salvar = QPushButton("Salvar Relatório (.txt)")
        self.btn_salvar.clicked.connect(self._salvar_relatorio)
        linha_acoes.addWidget(self.btn_salvar)
        linha_acoes.addStretch()
        lay_res.addLayout(linha_acoes)

    def _quebrar_todas(self) -> None:
        texto = self.txt_cifrado.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Entrada Vazia", "Insira o texto cifrado a ser analisado.")
            return

        chave_max = self.spn_chave_max.value()
        self.btn_analisar_tudo.setEnabled(False)
        self.txt_relatorio.setPlainText("Executando testes estatísticos, análise de frequência e busca estocástica...")

        def _tarefa(ctx: Any = None) -> Dict[str, Any]:
            return analisar_texto(texto, maximo_chave=chave_max)

        def _sucesso(resultado: Dict[str, Any]) -> None:
            self.btn_analisar_tudo.setEnabled(True)
            self._resultado = resultado

            # 1. Relatório
            rel = gerar_relatorio(resultado, maximo_chave=chave_max)
            self.txt_relatorio.setPlainText(rel)

            # 2. César
            res_cesar = resultado.get("cesar", {})
            desloc = res_cesar.get("deslocamento", 0)
            qui = res_cesar.get("qui_quadrado", 0.0)
            self.lbl_cesar_resumo.setText(
                f"Melhor Deslocamento Encontrado: {desloc} (Qui-quadrado: {qui:.2f})"
            )

            candidatos = res_cesar.get("ranking", [])
            self.tabela_cesar.setRowCount(len(candidatos))
            for i, cand in enumerate(candidatos):
                item_d = QTableWidgetItem(f"+{cand['deslocamento']} posições")
                item_p = QTableWidgetItem(f"{cand['qui_quadrado']:.2f}")
                item_t = QTableWidgetItem(cand["texto"][:120])
                if cand["deslocamento"] == desloc:
                    item_d.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item_p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item_t.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tabela_cesar.setItem(i, 0, item_d)
                self.tabela_cesar.setItem(i, 1, item_p)
                self.tabela_cesar.setItem(i, 2, item_t)

            # 3. Vigenère
            res_vig = resultado.get("vigenere", {})
            chave = res_vig.get("chave", "--")
            score_vig = res_vig.get("pontuacao", 0.0)
            self.lbl_vig_chave.setText(f"Chave Provável Detectada: '{chave}' (Score: {score_vig:.2f})")
            self.txt_vig_decifrado.setPlainText(res_vig.get("texto", ""))

            # 4. Substituição
            res_sub = resultado.get("substituicao", {})
            mapa = res_sub.get("mapeamento", {})
            mapa_str = " ".join(f"{k}->{v}" for k, v in sorted(mapa.items())[:13])
            self.lbl_sub_info.setText(f"Amostra do Mapeamento: {mapa_str}...")
            self.txt_sub_decifrado.setPlainText(res_sub.get("texto", ""))

        def _erro(msg: str) -> None:
            self.btn_analisar_tudo.setEnabled(True)
            mostrar_erro(self, "Falha na Criptoanálise", f"Erro:\n{msg}")

        executar_assincrono(self, _tarefa, ao_concluir=_sucesso, ao_falhar=_erro)

    def _salvar_relatorio(self) -> None:
        texto = self.txt_relatorio.toPlainText().strip()
        if not texto:
            mostrar_erro(self, "Aviso", "Não há relatório gerado para salvar.")
            return
        salvar_texto(self, texto, "Salvar Relatório de Criptoanálise Clássica", "criptoanalise_classica.txt")
