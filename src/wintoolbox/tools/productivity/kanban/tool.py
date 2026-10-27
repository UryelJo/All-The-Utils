"""
Interface de usuário para o Quadro Kanban offline com Fluent Design.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.kanban.logic import (
    ChecklistItem,
    KanbanBoard,
    KanbanCard,
    KanbanColumn,
    add_card,
    add_column,
    create_default_board,
    load_board_from_json,
    move_card,
    remove_card,
    remove_column,
    save_board_to_json,
    update_card,
)


class CardEditDialog(QDialog):
    """Diálogo para edição detalhada de um cartão Kanban."""

    def __init__(self, card: KanbanCard, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Cartão")
        self.resize(450, 520)
        self.card = card
        self.color = card.color

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()

        self.txt_title = QLineEdit(card.title)
        form.addRow("Título:", self.txt_title)

        self.txt_desc = QTextEdit(card.description)
        self.txt_desc.setMaximumHeight(80)
        form.addRow("Descrição:", self.txt_desc)

        self.txt_tags = QLineEdit(", ".join(card.tags))
        form.addRow("Etiquetas (separadas por vírgula):", self.txt_tags)

        # Prazo
        due_box = QHBoxLayout()
        self.dt_due = QDateEdit()
        self.dt_due.setCalendarPopup(True)
        if card.due_date:
            self.dt_due.setDate(QDate.fromString(card.due_date, "yyyy-MM-dd"))
        else:
            self.dt_due.setDate(QDate.currentDate())
        due_box.addWidget(self.dt_due)

        self.btn_clear_due = QPushButton("Sem Prazo")
        self.btn_clear_due.clicked.connect(lambda: self.dt_due.setDate(QDate()))
        due_box.addWidget(self.btn_clear_due)
        form.addRow("Prazo de Entrega:", due_box)

        # Cor
        color_box = QHBoxLayout()
        self.lbl_color_preview = QLabel("       ")
        self.lbl_color_preview.setStyleSheet(f"background-color: {self.color}; border-radius: 4px; border: 1px solid #666;")
        btn_pick_color = QPushButton("Escolher Cor...")
        btn_pick_color.clicked.connect(self._pick_color)
        color_box.addWidget(self.lbl_color_preview)
        color_box.addWidget(btn_pick_color)
        color_box.addStretch()
        form.addRow("Cor de Destaque:", color_box)

        layout.addLayout(form)

        # Checklist
        layout.addWidget(QLabel("<b>Subtarefas / Checklist:</b>"))
        self.list_check = QListWidget()
        for chk in card.checklist:
            item = QListWidgetItem(chk.title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if chk.completed else Qt.CheckState.Unchecked)
            self.list_check.addItem(item)
        layout.addWidget(self.list_check)

        chk_bar = QHBoxLayout()
        self.txt_new_chk = QLineEdit()
        self.txt_new_chk.setPlaceholderText("Nova subtarefa...")
        btn_add_chk = QPushButton("Adicionar")
        btn_add_chk.clicked.connect(self._add_chk_item)
        btn_rem_chk = QPushButton("Remover")
        btn_rem_chk.clicked.connect(self._rem_chk_item)
        chk_bar.addWidget(self.txt_new_chk, 1)
        chk_bar.addWidget(btn_add_chk)
        chk_bar.addWidget(btn_rem_chk)
        layout.addLayout(chk_bar)

        # Botões Salvar / Cancelar
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Salvar Alterações")
        btn_save.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self, "Selecionar Cor do Cartão")
        if c.isValid():
            self.color = c.name()
            self.lbl_color_preview.setStyleSheet(f"background-color: {self.color}; border-radius: 4px; border: 1px solid #666;")

    def _add_chk_item(self) -> None:
        t = self.txt_new_chk.text().strip()
        if t:
            item = QListWidgetItem(t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_check.addItem(item)
            self.txt_new_chk.clear()

    def _rem_chk_item(self) -> None:
        row = self.list_check.currentRow()
        if row >= 0:
            self.list_check.takeItem(row)

    def _on_save(self) -> None:
        title = self.txt_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Aviso", "O título do cartão não pode estar vazio.")
            return

        self.card.title = title
        self.card.description = self.txt_desc.toPlainText().strip()
        self.card.color = self.color
        tags_raw = [t.strip() for t in self.txt_tags.text().split(",") if t.strip()]
        self.card.tags = tags_raw

        due = self.dt_due.date()
        self.card.due_date = due.toString("yyyy-MM-dd") if due.isValid() and due > QDate(2000, 1, 1) else None

        chk_list = []
        for i in range(self.list_check.count()):
            it = self.list_check.item(i)
            chk_list.append(ChecklistItem(
                id=str(i),
                title=it.text(),
                completed=(it.checkState() == Qt.CheckState.Checked)
            ))
        self.card.checklist = chk_list

        self.accept()


@register
class KanbanTool(Tool):
    """Quadro de organização de tarefas estilo Kanban com colunas e cartões com checklists."""

    id = "productivity.kanban"
    name = "Quadro Kanban de Tarefas"
    description = "Organize seus projetos visualmente em colunas com cartões, checklists, tags e prazos de entrega 100% offline."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "kanban_board.json"
        self.board: KanbanBoard = load_board_from_json(self.storage_path)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Quadro Kanban de Tarefas")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Arraste e organize suas atividades por etapas. Suas alterações são salvas automaticamente.")
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_add_col = QPushButton("+ Nova Coluna")
        btn_add_col.clicked.connect(self._on_add_column)
        top_bar.addWidget(btn_add_col)

        btn_export = QPushButton("Exportar JSON")
        btn_export.clicked.connect(self._on_export)
        top_bar.addWidget(btn_export)

        btn_import = QPushButton("Importar JSON")
        btn_import.clicked.connect(self._on_import)
        top_bar.addWidget(btn_import)

        layout.addLayout(top_bar)

        # Scroll Area Horizontal para as colunas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.board_container = QWidget()
        self.board_layout = QHBoxLayout(self.board_container)
        self.board_layout.setContentsMargins(5, 5, 5, 5)
        self.board_layout.setSpacing(15)
        self.board_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.board_container)
        layout.addWidget(self.scroll_area, 1)

        self._refresh_board_ui()
        return widget

    def _save_state(self) -> None:
        save_board_to_json(self.board, self.storage_path)

    def _refresh_board_ui(self) -> None:
        # Limpa layout existente
        while self.board_layout.count() > 0:
            item = self.board_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Reconstrói colunas
        for col_idx, col in enumerate(self.board.columns):
            col_widget = self._create_column_widget(col, col_idx)
            self.board_layout.addWidget(col_widget)

    def _create_column_widget(self, col: KanbanColumn, col_idx: int) -> QWidget:
        col_frame = QFrame()
        col_frame.setFixedWidth(290)
        col_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; border: 1px solid rgba(128, 128, 128, 0.2); }"
        )

        col_layout = QVBoxLayout(col_frame)
        col_layout.setContentsMargins(10, 10, 10, 10)
        col_layout.setSpacing(8)

        # Cabeçalho da coluna
        head_box = QHBoxLayout()
        title_lbl = QLabel(f"<b>{col.title}</b> ({len(col.cards)})")
        title_lbl.setStyleSheet("font-size: 14px; border: none;")
        head_box.addWidget(title_lbl, 1)

        btn_del_col = QPushButton("×")
        btn_del_col.setFixedSize(22, 22)
        btn_del_col.setToolTip("Excluir coluna")
        btn_del_col.setStyleSheet("border: none; font-weight: bold; font-size: 14px; color: #888;")
        btn_del_col.clicked.connect(lambda _, c_id=col.id: self._on_delete_column(c_id))
        head_box.addWidget(btn_del_col)
        col_layout.addLayout(head_box)

        # Botão + Adicionar Cartão
        btn_new_card = QPushButton("+ Adicionar Cartão")
        btn_new_card.setStyleSheet("padding: 4px; border-radius: 4px;")
        btn_new_card.clicked.connect(lambda _, c_id=col.id: self._on_add_card(c_id))
        col_layout.addWidget(btn_new_card)

        # Scroll vertical para os cards da coluna
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setStyleSheet("border: none; background: transparent;")
        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for card in col.cards:
            card_widget = self._create_card_widget(card, col.id, col_idx)
            cards_layout.addWidget(card_widget)

        cards_scroll.setWidget(cards_container)
        col_layout.addWidget(cards_scroll, 1)

        return col_frame

    def _create_card_widget(self, card: KanbanCard, col_id: str, col_idx: int) -> QWidget:
        card_frame = QFrame()
        card_frame.setStyleSheet(
            f"QFrame {{ background-color: rgba(128, 128, 128, 0.12); border-left: 4px solid {card.color}; "
            "border-radius: 6px; padding: 6px; }"
        )

        v_layout = QVBoxLayout(card_frame)
        v_layout.setContentsMargins(6, 6, 6, 6)
        v_layout.setSpacing(4)

        # Título
        lbl_title = QLabel(f"<b>{card.title}</b>")
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("border: none;")
        v_layout.addWidget(lbl_title)

        # Descrição
        if card.description:
            lbl_desc = QLabel(card.description[:100] + ("..." if len(card.description) > 100 else ""))
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #888; font-size: 11px; border: none;")
            v_layout.addWidget(lbl_desc)

        # Checklist info
        if card.checklist:
            done_count = sum(1 for chk in card.checklist if chk.completed)
            lbl_chk = QLabel(f"✓ {done_count}/{len(card.checklist)}")
            lbl_chk.setStyleSheet("font-size: 10px; color: #16a34a; font-weight: bold; border: none;")
            v_layout.addWidget(lbl_chk)

        # Prazo
        if card.due_date:
            lbl_due = QLabel(f"Prazo: {card.due_date}")
            lbl_due.setStyleSheet("font-size: 10px; color: #ea580c; border: none;")
            v_layout.addWidget(lbl_due)

        # Tags
        if card.tags:
            tags_txt = " ".join([f"#{t}" for t in card.tags])
            lbl_tags = QLabel(tags_txt)
            lbl_tags.setStyleSheet("font-size: 10px; color: #0284c7; border: none;")
            v_layout.addWidget(lbl_tags)

        # Botões de Ação do Card
        actions = QHBoxLayout()
        actions.setSpacing(4)

        # Mover esquerda
        if col_idx > 0:
            btn_left = QPushButton("←")
            btn_left.setFixedSize(24, 20)
            btn_left.setToolTip("Mover para coluna anterior")
            prev_col_id = self.board.columns[col_idx - 1].id
            btn_left.clicked.connect(lambda _, c_id=card.id, t_id=prev_col_id: self._move_card(c_id, t_id))
            actions.addWidget(btn_left)

        btn_edit = QPushButton("Editar")
        btn_edit.setFixedHeight(20)
        btn_edit.clicked.connect(lambda _, c=card: self._edit_card(c))
        actions.addWidget(btn_edit, 1)

        btn_del = QPushButton("×")
        btn_del.setFixedSize(20, 20)
        btn_del.setToolTip("Remover cartão")
        btn_del.clicked.connect(lambda _, c_id=card.id: self._remove_card(c_id))
        actions.addWidget(btn_del)

        # Mover direita
        if col_idx < len(self.board.columns) - 1:
            btn_right = QPushButton("→")
            btn_right.setFixedSize(24, 20)
            btn_right.setToolTip("Mover para próxima coluna")
            next_col_id = self.board.columns[col_idx + 1].id
            btn_right.clicked.connect(lambda _, c_id=card.id, t_id=next_col_id: self._move_card(c_id, t_id))
            actions.addWidget(btn_right)

        v_layout.addLayout(actions)
        return card_frame

    def _on_add_column(self) -> None:
        title, ok = QInputDialog.getText(None, "Nova Coluna", "Nome da coluna:")
        if ok and title.strip():
            add_column(self.board, title.strip())
            self._save_state()
            self._refresh_board_ui()

    def _on_delete_column(self, col_id: str) -> None:
        reply = QMessageBox.question(
            None,
            "Excluir Coluna",
            "Deseja realmente remover esta coluna e todos os seus cartões?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            remove_column(self.board, col_id)
            self._save_state()
            self._refresh_board_ui()

    def _on_add_card(self, col_id: str) -> None:
        title, ok = QInputDialog.getText(None, "Novo Cartão", "Título da tarefa:")
        if ok and title.strip():
            import uuid
            card = KanbanCard(id=str(uuid.uuid4()), title=title.strip())
            add_card(self.board, col_id, card)
            self._save_state()
            self._refresh_board_ui()

    def _edit_card(self, card: KanbanCard) -> None:
        dlg = CardEditDialog(card)
        if dlg.exec():
            update_card(self.board, card)
            self._save_state()
            self._refresh_board_ui()

    def _remove_card(self, card_id: str) -> None:
        remove_card(self.board, card_id)
        self._save_state()
        self._refresh_board_ui()

    def _move_card(self, card_id: str, target_col_id: str) -> None:
        move_card(self.board, card_id, target_col_id)
        self._save_state()
        self._refresh_board_ui()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Exportar Quadro Kanban", "quadro_kanban.json", "JSON (*.json)")
        if path:
            try:
                save_board_to_json(self.board, Path(path))
                QMessageBox.information(None, "Sucesso", "Quadro Kanban exportado com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar quadro:\n{e}")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Importar Quadro Kanban", "", "JSON (*.json)")
        if path:
            try:
                self.board = load_board_from_json(Path(path))
                self._save_state()
                self._refresh_board_ui()
                QMessageBox.information(None, "Sucesso", "Quadro Kanban importado com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao importar quadro:\n{e}")
