"""
Interface de usuário para Gerenciador e Expansor de Trechos de Texto (Snippets).
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.snippets.logic import (
    Snippet,
    expand_snippet_body,
    filter_snippets,
    get_default_snippets,
    load_snippets_from_json,
    save_snippets_to_json,
)


@register
class SnippetsTool(Tool):
    """Gerenciador e expansor de trechos de texto frequentes com variáveis dinâmicas."""

    id = "productivity.snippets"
    name = "Expansor de Texto (Snippets)"
    description = "Armazene e expanda trechos de texto frequentes, modelos de e-mail e atas com substituição dinâmica de datas e variáveis."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "snippets.json"
        self.snippets: List[Snippet] = load_snippets_from_json(self.storage_path)
        self.selected_snippet: Optional[Snippet] = None

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Expansor de Trechos de Texto (Snippets)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Crie atalhos e modelos de texto com substituição inteligente de data, hora e área de transferência."
        )
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_new = QPushButton("+ Novo Snippet")
        btn_new.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 12px;")
        btn_new.clicked.connect(self._on_new_snippet)
        top_bar.addWidget(btn_new)

        btn_export = QPushButton("Exportar...")
        btn_export.clicked.connect(self._on_export)
        top_bar.addWidget(btn_export)

        btn_import = QPushButton("Importar...")
        btn_import.clicked.connect(self._on_import)
        top_bar.addWidget(btn_import)

        layout.addLayout(top_bar)

        # Divisão em duas colunas (Splitter)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Busca e Lista
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Filtro de busca
        filter_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar por atalho, título ou conteúdo...")
        self.txt_search.textChanged.connect(self._refresh_list)
        filter_bar.addWidget(self.txt_search, 2)

        self.cmb_category = QComboBox()
        self.cmb_category.addItem("Todas")
        self.cmb_category.currentTextChanged.connect(self._refresh_list)
        filter_bar.addWidget(self.cmb_category, 1)
        left_layout.addLayout(filter_bar)

        # Tabela de Snippets
        self.tbl_snippets = QTableWidget(0, 3)
        self.tbl_snippets.setHorizontalHeaderLabels(["Atalho", "Título", "Categoria"])
        self.tbl_snippets.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_snippets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_snippets.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_snippets.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_snippets.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tbl_snippets.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_snippets.itemSelectionChanged.connect(self._on_select_snippet)
        left_layout.addWidget(self.tbl_snippets)

        splitter.addWidget(left_widget)

        # Painel Direito: Edição e Expansão
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        form = QFormLayout()
        self.txt_edit_shortcut = QLineEdit()
        self.txt_edit_shortcut.setPlaceholderText("ex: :email ou ;msg")
        form.addRow("Atalho / Trigger:", self.txt_edit_shortcut)

        self.txt_edit_title = QLineEdit()
        form.addRow("Título:", self.txt_edit_title)

        self.txt_edit_category = QLineEdit("Geral")
        form.addRow("Categoria:", self.txt_edit_category)
        right_layout.addLayout(form)

        # Barra de inserção de tags rápidas
        var_bar = QHBoxLayout()
        var_bar.addWidget(QLabel("Inserir variável:"))
        for tag in ["{date}", "{time}", "{datetime}", "{clipboard}", "{uuid}"]:
            btn_tag = QPushButton(tag)
            btn_tag.setFixedHeight(22)
            btn_tag.setStyleSheet("font-size: 11px;")
            btn_tag.clicked.connect(lambda _, t=tag: self._insert_variable(t))
            var_bar.addWidget(btn_tag)
        var_bar.addStretch()
        right_layout.addLayout(var_bar)

        # Editor de texto
        right_layout.addWidget(QLabel("<b>Conteúdo do Trecho:</b>"))
        self.txt_edit_body = QTextEdit()
        self.txt_edit_body.textChanged.connect(self._update_preview)
        right_layout.addWidget(self.txt_edit_body, 2)

        # Pré-visualização com placeholders expandidos
        right_layout.addWidget(QLabel("<b>Pré-visualização do Texto Expandido:</b>"))
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet("background-color: rgba(128, 128, 128, 0.08);")
        right_layout.addWidget(self.txt_preview, 1)

        # Ações do Snippet
        btn_action_box = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar Texto Expandido")
        self.btn_copy.setStyleSheet("font-weight: bold; background-color: #16a34a; color: white; padding: 6px 12px;")
        self.btn_copy.clicked.connect(self._copy_expanded)
        btn_action_box.addWidget(self.btn_copy)

        self.lbl_copy_status = QLabel("")
        self.lbl_copy_status.setStyleSheet("color: #16a34a; font-weight: bold;")
        btn_action_box.addWidget(self.lbl_copy_status)
        btn_action_box.addStretch()

        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setStyleSheet("color: #dc2626;")
        self.btn_delete.clicked.connect(self._delete_snippet)
        btn_action_box.addWidget(self.btn_delete)

        self.btn_save = QPushButton("Salvar Alterações")
        self.btn_save.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 12px;")
        self.btn_save.clicked.connect(self._save_current_snippet)
        btn_action_box.addWidget(self.btn_save)

        right_layout.addLayout(btn_action_box)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 520])

        layout.addWidget(splitter, 1)

        self._update_categories_combo()
        self._refresh_list()
        if self.tbl_snippets.rowCount() > 0:
            self.tbl_snippets.selectRow(0)

        return widget

    def _insert_variable(self, tag: str) -> None:
        self.txt_edit_body.insertPlainText(tag)

    def _update_categories_combo(self) -> None:
        cur = self.cmb_category.currentText()
        cats = sorted(list(set(s.category for s in self.snippets)))
        self.cmb_category.blockSignals(True)
        self.cmb_category.clear()
        self.cmb_category.addItem("Todas")
        for c in cats:
            self.cmb_category.addItem(c)
        idx = self.cmb_category.findText(cur)
        if idx >= 0:
            self.cmb_category.setCurrentIndex(idx)
        self.cmb_category.blockSignals(False)

    def _refresh_list(self) -> None:
        query = self.txt_search.text()
        cat = self.cmb_category.currentText()
        filtered = filter_snippets(self.snippets, query, cat)

        self.tbl_snippets.blockSignals(True)
        self.tbl_snippets.setRowCount(0)
        for s in filtered:
            r = self.tbl_snippets.rowCount()
            self.tbl_snippets.insertRow(r)
            it_short = QTableWidgetItem(s.shortcut)
            it_short.setData(Qt.ItemDataRole.UserRole, s.id)
            it_title = QTableWidgetItem(s.title)
            it_cat = QTableWidgetItem(s.category)
            self.tbl_snippets.setItem(r, 0, it_short)
            self.tbl_snippets.setItem(r, 1, it_title)
            self.tbl_snippets.setItem(r, 2, it_cat)
        self.tbl_snippets.blockSignals(False)

    def _on_select_snippet(self) -> None:
        rows = self.tbl_snippets.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item = self.tbl_snippets.item(row, 0)
        if not item:
            return
        s_id = item.data(Qt.ItemDataRole.UserRole)
        for s in self.snippets:
            if s.id == s_id:
                self.selected_snippet = s
                self.txt_edit_shortcut.setText(s.shortcut)
                self.txt_edit_title.setText(s.title)
                self.txt_edit_category.setText(s.category)
                self.txt_edit_body.setPlainText(s.body)
                self.lbl_copy_status.clear()
                self._update_preview()
                break

    def _update_preview(self) -> None:
        raw = self.txt_edit_body.toPlainText()
        cb_text = QApplication.clipboard().text()
        expanded = expand_snippet_body(raw, cb_text)
        self.txt_preview.setPlainText(expanded)

    def _copy_expanded(self) -> None:
        text = self.txt_preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.lbl_copy_status.setText("Copiado com sucesso!")
            if self.selected_snippet:
                self.selected_snippet.usage_count += 1
                save_snippets_to_json(self.snippets, self.storage_path)

    def _on_new_snippet(self) -> None:
        import uuid
        novo = Snippet(
            id=str(uuid.uuid4()),
            shortcut=":novo",
            title="Novo Snippet",
            body="Texto de exemplo com {date}."
        )
        self.snippets.insert(0, novo)
        save_snippets_to_json(self.snippets, self.storage_path)
        self._update_categories_combo()
        self._refresh_list()
        self.tbl_snippets.selectRow(0)

    def _save_current_snippet(self) -> None:
        if not self.selected_snippet:
            return
        self.selected_snippet.shortcut = self.txt_edit_shortcut.text().strip()
        self.selected_snippet.title = self.txt_edit_title.text().strip() or "Sem título"
        self.selected_snippet.category = self.txt_edit_category.text().strip() or "Geral"
        self.selected_snippet.body = self.txt_edit_body.toPlainText()

        save_snippets_to_json(self.snippets, self.storage_path)
        self._update_categories_combo()
        self._refresh_list()
        self.lbl_copy_status.setText("Alterações salvas!")

    def _delete_snippet(self) -> None:
        if not self.selected_snippet:
            return
        reply = QMessageBox.question(
            None,
            "Excluir Snippet",
            f"Deseja excluir o snippet '{self.selected_snippet.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.snippets = [s for s in self.snippets if s.id != self.selected_snippet.id]
            self.selected_snippet = None
            save_snippets_to_json(self.snippets, self.storage_path)
            self._update_categories_combo()
            self._refresh_list()
            self.txt_edit_shortcut.clear()
            self.txt_edit_title.clear()
            self.txt_edit_body.clear()
            self.txt_preview.clear()
            self.lbl_copy_status.clear()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Exportar Snippets", "snippets.json", "JSON (*.json)")
        if path:
            try:
                save_snippets_to_json(self.snippets, Path(path))
                QMessageBox.information(None, "Sucesso", "Snippets exportados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar snippets:\n{e}")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Importar Snippets", "", "JSON (*.json)")
        if path:
            try:
                imported = load_snippets_from_json(Path(path))
                self.snippets = imported
                save_snippets_to_json(self.snippets, self.storage_path)
                self._update_categories_combo()
                self._refresh_list()
                QMessageBox.information(None, "Sucesso", "Snippets importados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao importar snippets:\n{e}")
