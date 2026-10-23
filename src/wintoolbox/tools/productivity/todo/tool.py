"""
Interface gráfica da ferramenta Lista de Tarefas (To-Do).
"""
from datetime import date
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.todo.logic import (
    PRIORITIES, add_todo, delete_todo, get_todo_categories, get_todo_stats,
    list_todos, toggle_todo_completed
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.todo.ui")


@register
class TodoTool(Tool):
    id = "productivity.todo"
    name = "Lista de Tarefas"
    category = "Produtividade"
    description = "Gerenciamento local e minimalista de afazeres com categorias, prioridades e prazos"
    keywords = ["todo", "tarefas", "afazeres", "produtividade", "checklist", "rotina", "metas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TodoView(self, parent)


class TodoView(QWidget):
    def __init__(self, tool: TodoTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._todos: List[Dict[str, Any]] = []

        self._build_ui()
        self._refresh_categories()
        self._refresh_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Lista de Tarefas (To-Do)",
            "Organização pessoal e profissional com persistência local, categorização e controle de prioridades."
        ))

        # 1. Painel de Resumo / Estatísticas
        self.stats_bar = QHBoxLayout()
        self.lbl_stats = QLabel("Carregando resumo...")
        self.lbl_stats.setStyleSheet("font-size: 12px; font-weight: 600; color: #60A5FA; padding: 2px 0;")
        self.stats_bar.addWidget(self.lbl_stats)
        self.stats_bar.addStretch(1)
        root.addLayout(self.stats_bar)

        # 2. Formulário de Nova Tarefa
        form_box = QGroupBox("Adicionar Nova Tarefa")
        grid = QGridLayout(form_box)
        grid.setSpacing(8)

        grid.addWidget(QLabel("Título:"), 0, 0)
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("Ex: Finalizar relatório de vendas, revisar código...")
        self.edit_title.returnPressed.connect(self._on_add_task)
        grid.addWidget(self.edit_title, 0, 1, 1, 3)

        grid.addWidget(QLabel("Categoria:"), 1, 0)
        self.combo_category = QComboBox()
        self.combo_category.setEditable(True)
        self.combo_category.addItems(["Geral", "Trabalho", "Estudos", "Pessoal", "Projetos"])
        grid.addWidget(self.combo_category, 1, 1)

        grid.addWidget(QLabel("Prioridade:"), 1, 2)
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(PRIORITIES)
        self.combo_priority.setCurrentText("Média")
        grid.addWidget(self.combo_priority, 1, 3)

        # Data de entrega
        due_row = QHBoxLayout()
        self.chk_due = QCheckBox("Definir Prazo:")
        self.chk_due.toggled.connect(self._toggle_due_input)
        due_row.addWidget(self.chk_due)

        self.date_due = QDateEdit()
        self.date_due.setCalendarPopup(True)
        self.date_due.setDate(QDate.currentDate())
        self.date_due.setEnabled(False)
        due_row.addWidget(self.date_due)
        due_row.addStretch(1)
        grid.addLayout(due_row, 2, 0, 1, 2)

        btn_add = QPushButton("Adicionar Tarefa")
        btn_add.setProperty("class", "primary")
        btn_add.setFixedWidth(140)
        btn_add.clicked.connect(self._on_add_task)
        grid.addWidget(btn_add, 2, 3, alignment=Qt.AlignmentFlag.AlignRight)

        root.addWidget(form_box)

        # 3. Barra de Filtros e Busca
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        # Status
        self.radio_all = QRadioButton("Todas")
        self.radio_pending = QRadioButton("Pendentes")
        self.radio_pending.setChecked(True)
        self.radio_completed = QRadioButton("Concluídas")

        self.radio_all.toggled.connect(self._refresh_list)
        self.radio_pending.toggled.connect(self._refresh_list)
        self.radio_completed.toggled.connect(self._refresh_list)

        filter_bar.addWidget(self.radio_pending)
        filter_bar.addWidget(self.radio_all)
        filter_bar.addWidget(self.radio_completed)
        filter_bar.addSpacing(12)

        # Busca
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Buscar tarefas...")
        self.edit_search.textChanged.connect(self._refresh_list)
        filter_bar.addWidget(self.edit_search, stretch=1)

        # Filtro de Categoria
        self.filter_category = QComboBox()
        self.filter_category.addItem("Todas as Categorias", "")
        self.filter_category.currentIndexChanged.connect(self._refresh_list)
        filter_bar.addWidget(self.filter_category)

        root.addLayout(filter_bar)

        # 4. Lista de Tarefas
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(6)
        root.addWidget(self.list_widget, stretch=1)

    def _toggle_due_input(self, checked: bool) -> None:
        self.date_due.setEnabled(checked)

    def _refresh_categories(self) -> None:
        cats = get_todo_categories()
        current_data = self.filter_category.currentData()
        self.filter_category.blockSignals(True)
        self.filter_category.clear()
        self.filter_category.addItem("Todas as Categorias", "")
        for c in cats:
            self.filter_category.addItem(c, c)
        idx = self.filter_category.findData(current_data)
        if idx >= 0:
            self.filter_category.setCurrentIndex(idx)
        self.filter_category.blockSignals(False)

    def _refresh_list(self) -> None:
        # Status
        if self.radio_pending.isChecked():
            status = "pending"
        elif self.radio_completed.isChecked():
            status = "completed"
        else:
            status = "all"

        cat = self.filter_category.currentData() or ""
        search = self.edit_search.text().strip()

        self._todos = list_todos(category=cat, filter_status=status, search=search)
        self.list_widget.clear()

        for todo_data in self._todos:
            item = QListWidgetItem()
            widget = self._create_todo_widget(todo_data)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        # Atualiza estatísticas
        stats = get_todo_stats()
        tot = stats["total"]
        comp = stats["completed"]
        pct = int((comp / tot) * 100) if tot > 0 else 0
        self.lbl_stats.setText(
            f"Total: {tot} tarefas  |  Pendentes: {stats['pending']}  |  Concluídas: {comp} ({pct}%)"
        )

    def _create_todo_widget(self, data: Dict[str, Any]) -> QWidget:
        container = QFrame()
        container.setProperty("class", "card")
        container.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px; }")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Checkbox de conclusão
        chk = QCheckBox()
        chk.setChecked(data["completed"])
        chk.toggled.connect(lambda checked=False, t_id=data["id"]: self._on_toggle_completed(t_id))
        layout.addWidget(chk)

        # Conteúdo do To-Do
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        lbl_title = QLabel(data["title"])
        lbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        if data["completed"]:
            lbl_title.setStyleSheet("color: rgba(255, 255, 255, 0.35); text-decoration: line-through;")
        text_layout.addWidget(lbl_title)

        # Metadados: Categoria, Prioridade, Prazo
        meta_parts = []
        if data["category"]:
            meta_parts.append(f"Projeto: {data['category']}")
        if data["priority"]:
            meta_parts.append(f"Prioridade: {data['priority']}")
        if data["due_date"]:
            meta_parts.append(f"Prazo: {data['due_date']}")

        lbl_meta = QLabel("  •  ".join(meta_parts))
        lbl_meta.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px;")
        text_layout.addWidget(lbl_meta)

        layout.addLayout(text_layout, stretch=1)

        # Botão Excluir
        btn_del = QPushButton("Excluir")
        btn_del.setFixedWidth(65)
        btn_del.clicked.connect(lambda checked=False, t_id=data["id"]: self._on_delete_task(t_id))
        layout.addWidget(btn_del)

        return container

    def _on_add_task(self) -> None:
        title = self.edit_title.text().strip()
        if not title:
            show_toast(self, "Digite um título para a tarefa.")
            return

        cat = self.combo_category.currentText().strip() or "Geral"
        prio = self.combo_priority.currentText()
        due = self.date_due.date().toString("dd/MM/yyyy") if self.chk_due.isChecked() else None

        try:
            add_todo(title=title, category=cat, priority=prio, due_date=due)
            self.edit_title.clear()
            self._refresh_categories()
            self._refresh_list()
            show_toast(self, "Tarefa adicionada!")
        except Exception as exc:
            show_toast(self, f"Erro: {exc}")

    def _on_toggle_completed(self, todo_id: int) -> None:
        toggle_todo_completed(todo_id)
        self._refresh_list()

    def _on_delete_task(self, todo_id: int) -> None:
        delete_todo(todo_id)
        self._refresh_list()
        self._refresh_categories()
