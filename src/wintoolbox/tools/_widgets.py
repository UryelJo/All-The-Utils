"""Componentes de interface reutilizados pelas novas ferramentas.

Mantém o visual Fluent do projeto, evita duplicação de HTML/CSS e centraliza a
execução assíncrona. Os widgets são criados apenas na thread principal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import TaskContext, ToolResult
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.log_panel import LogPanelWidget
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader


def criar_card(titulo: Optional[str] = None, parent: Optional[QWidget] = None) -> tuple[QFrame, QVBoxLayout]:
    """Cria um cartão padrão e devolve (frame, layout vertical)."""
    card = QFrame(parent)
    card.setObjectName("Card")
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    if titulo:
        label = QLabel(titulo)
        label.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(label)
    return card, layout


def criar_aviso(texto: str, parent: Optional[QWidget] = None, destaque: bool = False) -> QFrame:
    """Cartão informativo discreto; ``destaque`` usa a cor de alerta do tema."""
    frame = QFrame(parent)
    frame.setObjectName("AvisoCard")
    frame.setStyleSheet(
        "QFrame#AvisoCard { border-left: 3px solid %s; background: rgba(255,255,255,0.04); "
        "border-radius: 4px; }" % ("#f59e0b" if destaque else "rgba(255,255,255,0.18)")
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 9, 12, 9)
    label = QLabel(texto)
    label.setWordWrap(True)
    label.setStyleSheet("font-size: 11px; color: rgba(255,255,255,0.72);")
    layout.addWidget(label)
    return frame


def botao_copiar(texto_getter: Callable[[], str], parent: Optional[QWidget] = None, rotulo: str = "Copiar") -> QPushButton:
    """Botão que copia o retorno de ``texto_getter`` para a área de transferência."""
    botao = QPushButton(rotulo, parent)

    def _copiar() -> None:
        texto = texto_getter() or ""
        if not texto.strip():
            show_toast(botao, "Nada para copiar", "O resultado ainda está vazio.", kind="warning")
            return
        QApplication.clipboard().setText(texto)
        show_toast(botao, "Copiado", "Conteúdo copiado para a área de transferência.", kind="success", duration_ms=1800)

    botao.clicked.connect(_copiar)
    return botao


class PainelFerramenta(QWidget):
    """Página padrão de ferramenta interativa, com rolagem e cabeçalho."""

    def __init__(self, tool: Any, parent: Optional[QWidget] = None, com_rolagem: bool = True) -> None:
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        if com_rolagem:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            conteudo = QWidget()
            self.layout_conteudo = QVBoxLayout(conteudo)
            scroll.setWidget(conteudo)
            raiz.addWidget(scroll)
        else:
            conteudo = self
            self.layout_conteudo = raiz

        self.layout_conteudo.setContentsMargins(20, 18, 20, 20)
        self.layout_conteudo.setSpacing(12)
        self.layout_conteudo.addWidget(ToolHeader(tool.name, tool.description))

    def adicionar(self, widget: QWidget, esticar: int = 0) -> QWidget:
        self.layout_conteudo.addWidget(widget, stretch=esticar)
        return widget

    def adicionar_card(self, titulo: Optional[str] = None) -> tuple[QFrame, QVBoxLayout]:
        card, layout = criar_card(titulo, self)
        self.adicionar(card)
        return card, layout

    def adicionar_aviso(self, texto: str, destaque: bool = False) -> QFrame:
        aviso = criar_aviso(texto, self, destaque)
        self.adicionar(aviso)
        return aviso

    def adicionar_espaco(self) -> None:
        self.layout_conteudo.addStretch(1)


class PainelOpcoes(QWidget):
    """Formulário usado como opções de uma FileTool."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.layout_opcoes = QVBoxLayout(self)
        self.layout_opcoes.setContentsMargins(12, 10, 12, 10)
        self.layout_opcoes.setSpacing(9)

    def adicionar(self, widget: QWidget) -> QWidget:
        self.layout_opcoes.addWidget(widget)
        return widget

    def adicionar_linha(self, *widgets: QWidget) -> QHBoxLayout:
        linha = QHBoxLayout()
        linha.setSpacing(8)
        for widget in widgets:
            linha.addWidget(widget)
        self.layout_opcoes.addLayout(linha)
        return linha


def criar_saida_texto(altura: int = 240, parent: Optional[QWidget] = None) -> QPlainTextEdit:
    """Área monoespaçada somente leitura para resultados e logs."""
    caixa = QPlainTextEdit(parent)
    caixa.setReadOnly(True)
    caixa.setFont(QFont("Cascadia Mono, Consolas", 9))
    caixa.setMinimumHeight(altura)
    caixa.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return caixa


def criar_tabela(colunas: List[str], parent: Optional[QWidget] = None) -> QTableWidget:
    """Tabela compacta com as colunas informadas."""
    tabela = QTableWidget(0, len(colunas), parent)
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.verticalHeader().setVisible(False)
    tabela.setAlternatingRowColors(True)
    tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return tabela


def preencher_tabela(tabela: QTableWidget, linhas: List[List[Any]]) -> None:
    """Substitui o conteúdo da tabela de forma atômica e segura."""
    from wintoolbox.ui.widgets.sortable_table import SmartTableWidgetItem, batch_table_update

    with batch_table_update(tabela):
        tabela.setRowCount(len(linhas))
        for r, linha in enumerate(linhas):
            for c, valor in enumerate(linha):
                item = SmartTableWidgetItem("" if valor is None else str(valor))
                tabela.setItem(r, c, item)


def mostrar_erro(parent: Optional[QWidget], titulo: str, erro: Exception | str) -> None:
    """Exibe erro de forma amigável, sem stacktrace."""
    mensagem = str(erro)
    show_toast(parent, titulo, mensagem, kind="error", duration_ms=5000)
    QMessageBox.warning(parent, titulo, mensagem)


def executar_assincrono(
    dono: QWidget,
    funcao: Callable[[TaskContext], Any],
    ao_concluir: Optional[Callable[[Any], None]] = None,
    ao_falhar: Optional[Callable[[Exception], None]] = None,
    ao_progredir: Optional[Callable[[int, int, str], None]] = None,
    ao_logar: Optional[Callable[[str, str], None]] = None,
) -> None:
    """Executa ``funcao`` no TaskRunner e entrega o valor bruto no callback.

    O TaskRunner do projeto entrega um ``ToolResult``. Este auxiliar embrulha o
    valor real em ``ToolResult.details[0]`` para que consumidores simples não
    precisem montar um resultado de lote.
    """
    runner = getattr(dono, "runner", None)
    if not isinstance(runner, TaskRunner):
        runner = TaskRunner()
        setattr(dono, "runner", runner)

    def _tarefa(ctx: TaskContext) -> ToolResult:
        valor = funcao(ctx)
        resultado = ToolResult(success=True, message="Concluído", items_total=1, items_success=1)
        resultado.details.append(valor)  # type: ignore[arg-type]
        return resultado

    def _concluiu(resultado: ToolResult) -> None:
        if ao_concluir is None:
            return
        if resultado.details:
            ao_concluir(resultado.details[0])
        else:
            ao_concluir(None)

    def _falhou(mensagem: str) -> None:
        if ao_falhar is not None:
            ao_falhar(RuntimeError(mensagem))

    runner.start_task(
        _tarefa,
        on_progress=ao_progredir,
        on_log=ao_logar,
        on_finished=_concluiu,
        on_error=_falhou,
    )


def adicionar_log_painel(painel: PainelFerramenta, titulo: str = "Log de Execução") -> LogPanelWidget:
    """Cria e adiciona o painel de log padrão à página."""
    log = LogPanelWidget(painel, title=titulo)
    painel.adicionar(log)
    return log


def texto_copiado() -> str:
    """Leitura defensiva da área de transferência."""
    return QApplication.clipboard().text() or ""
