"""
Interface gráfica do Bloco de Anotações Rápidas.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.productivity.quick_notes.logic import (
    count_words_and_chars, create_note, delete_note, export_note_text,
    get_note_by_id, list_notes, toggle_note_pin, update_note
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("productivity.quick_notes.ui")


@register
class QuickNotesTool(Tool):
    id = "productivity.quick_notes"
    name = "Bloco de Notas Rápidas"
    category = "Produtividade"
    description = "Anotações com salvamento automático em tempo real, suporte a notas fixadas e busca instantânea"
    keywords = ["notas", "bloco de notas", "anotacoes", "scratchpad", "rascunho", "texto", "memo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return QuickNotesView(self, parent)


class QuickNotesView(QWidget):
    def __init__(self, tool: QuickNotesTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_note_id: Optional[int] = None
        self._notes: List[Dict[str, Any]] = []
        self._is_loading_note = False

        # Timer de autosave (debounce 600ms)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._auto_save_current_note)

        self._build_ui()
        self._refresh_notes_list()

        # Seleciona a primeira nota ou cria uma inicial
        if self._notes:
            self._select_note_by_id(self._notes[0]["id"])
        else:
            self._create_new_note()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        root.addWidget(ToolHeader(
            "Bloco de Anotações Rápidas",
            "Suas ideias, lembretes e textos organizados localmente com salvamento instantâneo e contadores de escrita."
        ))

        # Splitter Horizontal
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Painel Esquerdo: Lista de Notas
        left_panel = QFrame()
        left_panel.setProperty("class", "card")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        # Botão Nova Nota
        btn_new = QPushButton("+ Nova Nota")
        btn_new.setProperty("class", "primary")
        btn_new.setFixedHeight(32)
        btn_new.clicked.connect(self._create_new_note)
        left_layout.addWidget(btn_new)

        # Busca
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Pesquisar notas...")
        self.edit_search.textChanged.connect(self._refresh_notes_list)
        left_layout.addWidget(self.edit_search)

        # Lista
        self.notes_list = QListWidget()
        self.notes_list.currentRowChanged.connect(self._on_note_selected)
        left_layout.addWidget(self.notes_list, stretch=1)

        splitter.addWidget(left_panel)

        # 2. Painel Direito: Editor
        right_panel = QFrame()
        right_panel.setProperty("class", "card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        # Barra Superior do Editor
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.edit_title = QLineEdit()
        self.edit_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.edit_title.setPlaceholderText("Título da Nota...")
        self.edit_title.textChanged.connect(self._trigger_autosave)
        top_bar.addWidget(self.edit_title, stretch=1)

        self.edit_category = QLineEdit()
        self.edit_category.setPlaceholderText("Categoria")
        self.edit_category.setFixedWidth(110)
        self.edit_category.textChanged.connect(self._trigger_autosave)
        top_bar.addWidget(self.edit_category)

        self.btn_pin = QPushButton("Fixar")
        self.btn_pin.setFixedWidth(70)
        self.btn_pin.clicked.connect(self._toggle_pin)
        top_bar.addWidget(self.btn_pin)

        btn_export = QPushButton("Exportar...")
        btn_export.setFixedWidth(80)
        btn_export.clicked.connect(self._export_note)
        top_bar.addWidget(btn_export)

        btn_del = QPushButton("Excluir")
        btn_del.setFixedWidth(65)
        btn_del.clicked.connect(self._delete_current_note)
        top_bar.addWidget(btn_del)

        right_layout.addLayout(top_bar)

        # Editor de Texto
        self.txt_content = QTextEdit()
        self.txt_content.setFont(QFont("Segoe UI", 10))
        self.txt_content.setPlaceholderText("Comece a digitar sua anotação aqui...")
        self.txt_content.textChanged.connect(self._on_content_changed)
        right_layout.addWidget(self.txt_content, stretch=1)

        # Barra de Status do Editor
        status_bar = QHBoxLayout()
        self.lbl_word_count = QLabel("0 palavras  •  0 caracteres")
        self.lbl_word_count.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 11px;")
        status_bar.addWidget(self.lbl_word_count)

        status_bar.addStretch(1)

        self.lbl_save_status = QLabel("Salvo automaticamente")
        self.lbl_save_status.setStyleSheet("color: #10B981; font-size: 11px;")
        status_bar.addWidget(self.lbl_save_status)

        right_layout.addLayout(status_bar)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter, stretch=1)

    def _refresh_notes_list(self) -> None:
        query = self.edit_search.text().strip()
        self._notes = list_notes(query=query)

        self.notes_list.blockSignals(True)
        self.notes_list.clear()

        selected_row = -1
        for i, note in enumerate(self._notes):
            pin_badge = "[Fixada] " if note["is_pinned"] else ""
            title_text = f"{pin_badge}{note['title']}"
            item = QListWidgetItem(title_text)
            self.notes_list.addItem(item)

            if self._current_note_id == note["id"]:
                selected_row = i

        if selected_row >= 0:
            self.notes_list.setCurrentRow(selected_row)

        self.notes_list.blockSignals(False)

    def _select_note_by_id(self, note_id: int) -> None:
        note = get_note_by_id(note_id)
        if not note:
            return

        self._is_loading_note = True
        self._current_note_id = note_id
        self.edit_title.setText(note["title"])
        self.edit_category.setText(note["category"])
        self.txt_content.setPlainText(note["content"])

        is_pinned = note["is_pinned"]
        self.btn_pin.setText("Desafixar" if is_pinned else "Fixar")

        self._update_stats(note["content"])
        self.lbl_save_status.setText("Salvo automaticamente")
        self._is_loading_note = False

        # Sincroniza seleção na lista
        for i, n in enumerate(self._notes):
            if n["id"] == note_id:
                self.notes_list.blockSignals(True)
                self.notes_list.setCurrentRow(i)
                self.notes_list.blockSignals(False)
                break

    def _on_note_selected(self, row: int) -> None:
        if 0 <= row < len(self._notes):
            self._select_note_by_id(self._notes[row]["id"])

    def _create_new_note(self) -> None:
        new_id = create_note(title="Nova Nota", content="")
        self._refresh_notes_list()
        self._select_note_by_id(new_id)
        self.edit_title.setFocus()
        self.edit_title.selectAll()

    def _on_content_changed(self) -> None:
        if self._is_loading_note:
            return
        self._update_stats(self.txt_content.toPlainText())
        self._trigger_autosave()

    def _update_stats(self, text: str) -> None:
        words, chars = count_words_and_chars(text)
        self.lbl_word_count.setText(f"{words} palavras  •  {chars} caracteres")

    def _trigger_autosave(self) -> None:
        if self._is_loading_note or not self._current_note_id:
            return
        self.lbl_save_status.setText("Salvando alterações...")
        self.lbl_save_status.setStyleSheet("color: #F59E0B; font-size: 11px;")
        self._save_timer.start()

    def _auto_save_current_note(self) -> None:
        if not self._current_note_id:
            return

        title = self.edit_title.text().strip() or "Sem título"
        cat = self.edit_category.text().strip() or "Geral"
        content = self.txt_content.toPlainText()

        update_note(self._current_note_id, title=title, content=content, category=cat)

        self.lbl_save_status.setText("Salvo automaticamente")
        self.lbl_save_status.setStyleSheet("color: #10B981; font-size: 11px;")
        self._refresh_notes_list()

    def _toggle_pin(self) -> None:
        if not self._current_note_id:
            return
        new_pinned = toggle_note_pin(self._current_note_id)
        self.btn_pin.setText("Desafixar" if new_pinned else "Fixar")
        self._refresh_notes_list()

    def _delete_current_note(self) -> None:
        if not self._current_note_id:
            return
        delete_note(self._current_note_id)
        self._current_note_id = None
        self._refresh_notes_list()
        if self._notes:
            self._select_note_by_id(self._notes[0]["id"])
        else:
            self._create_new_note()
        show_toast(self, "Nota excluída com sucesso.")

    def _export_note(self) -> None:
        if not self._current_note_id:
            return
        note = get_note_by_id(self._current_note_id)
        if not note:
            return

        default_name = f"{note['title']}.md".replace("/", "-").replace("\\", "-")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Nota", default_name, "Markdown (*.md);;Texto (*.txt)")
        if path:
            fmt = "md" if path.endswith(".md") else "txt"
            exported = export_note_text(note, format_type=fmt)
            Path(path).write_text(exported, encoding="utf-8")
            show_toast(self, f"Nota exportada com sucesso em {Path(path).name}!")
