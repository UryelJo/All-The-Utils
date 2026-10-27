"""
Interface de usuário para o Gerenciador Local de Favoritos e Links Web.
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.bookmarks.logic import (
    Bookmark,
    check_url_status,
    export_netscape_bookmarks_html,
    filter_bookmarks,
    import_netscape_bookmarks_html,
    load_bookmarks_json,
    save_bookmarks_json,
)


class BookmarkEditDialog(QDialog):
    """Diálogo para adicionar ou editar um link favorito."""

    def __init__(self, bookmark: Optional[Bookmark] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Favorito")
        self.resize(420, 280)
        self.bookmark = bookmark

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_title = QLineEdit(bookmark.title if bookmark else "")
        form.addRow("Título / Nome:", self.txt_title)

        self.txt_url = QLineEdit(bookmark.url if bookmark else "https://")
        form.addRow("Endereço URL:", self.txt_url)

        self.txt_tags = QLineEdit(", ".join(bookmark.tags) if bookmark else "")
        form.addRow("Tags (separadas por vírgula):", self.txt_tags)

        self.txt_notes = QTextEdit(bookmark.notes if bookmark else "")
        self.txt_notes.setMaximumHeight(70)
        form.addRow("Anotações:", self.txt_notes)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_canc = QPushButton("Cancelar")
        btn_canc.clicked.connect(self.reject)
        btn_save = QPushButton("Salvar")
        btn_save.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white;")
        btn_save.clicked.connect(self.accept)
        btns.addWidget(btn_canc)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str, List[str], str]:
        t = self.txt_title.text().strip() or "Link"
        u = self.txt_url.text().strip()
        tags = [tag.strip() for tag in self.txt_tags.text().split(",") if tag.strip()]
        notes = self.txt_notes.toPlainText().strip()
        return t, u, tags, notes


@register
class BookmarksTool(Tool):
    """Gerenciador local de links e referências web com verificador de status."""

    id = "productivity.bookmarks"
    name = "Gerenciador de Links e Favoritos"
    description = "Organize seus links e artigos salvos com tags, busca rápida, verificador de links quebrados e importação de navegadores."
    category = "Produtividade"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "bookmarks.json"
        self.bookmarks: List[Bookmark] = load_bookmarks_json(self.storage_path)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Gerenciador de Links e Favoritos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel("Seus links essenciais salvos com privacidade total. Importe de navegadores e verifique links ativos.")
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_new = QPushButton("+ Novo Favorito")
        btn_new.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 14px;")
        btn_new.clicked.connect(self._on_new_bookmark)
        top_bar.addWidget(btn_new)

        btn_check = QPushButton("Verificar Links")
        btn_check.setToolTip("Checa a resposta HTTP de todos os links da lista")
        btn_check.clicked.connect(self._on_check_all_links)
        top_bar.addWidget(btn_check)

        btn_import = QPushButton("Importar HTML...")
        btn_import.clicked.connect(self._on_import_html)
        top_bar.addWidget(btn_import)

        btn_export = QPushButton("Exportar...")
        btn_export.clicked.connect(self._on_export)
        top_bar.addWidget(btn_export)

        layout.addLayout(top_bar)

        # Filtros
        filter_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar por título, URL, notas ou tag...")
        self.txt_search.textChanged.connect(self._refresh_table)
        filter_bar.addWidget(self.txt_search, 2)

        filter_bar.addWidget(QLabel("Filtrar por Tag:"))
        self.cmb_tag = QComboBox()
        self.cmb_tag.addItem("Todas")
        self.cmb_tag.currentTextChanged.connect(self._refresh_table)
        filter_bar.addWidget(self.cmb_tag, 1)
        layout.addLayout(filter_bar)

        # Tabela de links
        self.tbl_links = QTableWidget(0, 5)
        self.tbl_links.setHorizontalHeaderLabels(["Status", "Título", "Endereço URL", "Tags", "Ações"])
        self.tbl_links.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_links.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_links.setColumnWidth(1, 220)
        self.tbl_links.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_links.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_links.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_links.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_links.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_links.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tbl_links, 1)

        self._update_tags_combo()
        self._refresh_table()
        return widget

    def _save_data(self) -> None:
        save_bookmarks_json(self.bookmarks, self.storage_path)

    def _update_tags_combo(self) -> None:
        all_tags = set()
        for b in self.bookmarks:
            all_tags.update(b.tags)
        cur = self.cmb_tag.currentText()
        self.cmb_tag.blockSignals(True)
        self.cmb_tag.clear()
        self.cmb_tag.addItem("Todas")
        for t in sorted(list(all_tags)):
            self.cmb_tag.addItem(t)
        idx = self.cmb_tag.findText(cur)
        if idx >= 0:
            self.cmb_tag.setCurrentIndex(idx)
        self.cmb_tag.blockSignals(False)

    def _refresh_table(self) -> None:
        q = self.txt_search.text()
        tag = self.cmb_tag.currentText()
        filtered = filter_bookmarks(self.bookmarks, q, tag)

        self.tbl_links.setRowCount(0)
        for b in filtered:
            r = self.tbl_links.rowCount()
            self.tbl_links.insertRow(r)

            # Status Icon
            if b.status == "active":
                st_txt = "● Ativo"
                st_color = "#16a34a"
            elif b.status == "broken":
                st_txt = "● Inativo"
                st_color = "#dc2626"
            else:
                st_txt = "○ Não testado"
                st_color = "#888888"

            it_st = QTableWidgetItem(st_txt)
            it_st.setForeground(Qt.GlobalColor.white if False else Qt.GlobalColor.black)
            it_st.setData(Qt.ItemDataRole.UserRole, b.id)

            it_title = QTableWidgetItem(b.title)
            it_url = QTableWidgetItem(b.url)
            it_tags = QTableWidgetItem(", ".join(b.tags))

            self.tbl_links.setItem(r, 0, it_st)
            self.tbl_links.setItem(r, 1, it_title)
            self.tbl_links.setItem(r, 2, it_url)
            self.tbl_links.setItem(r, 3, it_tags)

            # Botões de Ação na célula
            act_widget = QWidget()
            h_box = QHBoxLayout(act_widget)
            h_box.setContentsMargins(2, 2, 2, 2)
            h_box.setSpacing(4)

            btn_open = QPushButton("Abrir")
            btn_open.setFixedHeight(22)
            btn_open.clicked.connect(lambda _, u=b.url: self._open_browser(u))
            h_box.addWidget(btn_open)

            btn_edit = QPushButton("Editar")
            btn_edit.setFixedHeight(22)
            btn_edit.clicked.connect(lambda _, item=b: self._edit_bookmark(item))
            h_box.addWidget(btn_edit)

            btn_del = QPushButton("×")
            btn_del.setFixedSize(22, 22)
            btn_del.setStyleSheet("color: #dc2626; font-weight: bold;")
            btn_del.clicked.connect(lambda _, item=b: self._delete_bookmark(item))
            h_box.addWidget(btn_del)

            self.tbl_links.setCellWidget(r, 4, act_widget)

    def _open_browser(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_double_click(self, row: int, col: int) -> None:
        it = self.tbl_links.item(row, 2)
        if it:
            self._open_browser(it.text())

    def _on_new_bookmark(self) -> None:
        dlg = BookmarkEditDialog(None)
        if dlg.exec():
            t, u, tags, notes = dlg.get_data()
            import uuid
            b = Bookmark(
                id=str(uuid.uuid4()),
                title=t,
                url=u,
                tags=tags,
                notes=notes
            )
            self.bookmarks.insert(0, b)
            self._save_data()
            self._update_tags_combo()
            self._refresh_table()

    def _edit_bookmark(self, item: Bookmark) -> None:
        dlg = BookmarkEditDialog(item)
        if dlg.exec():
            t, u, tags, notes = dlg.get_data()
            item.title = t
            item.url = u
            item.tags = tags
            item.notes = notes
            self._save_data()
            self._update_tags_combo()
            self._refresh_table()

    def _delete_bookmark(self, item: Bookmark) -> None:
        reply = QMessageBox.question(
            None,
            "Excluir Favorito",
            f"Deseja excluir o link '{item.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.bookmarks = [b for b in self.bookmarks if b.id != item.id]
            self._save_data()
            self._update_tags_combo()
            self._refresh_table()

    def _on_check_all_links(self) -> None:
        for b in self.bookmarks:
            is_ok, code, msg = check_url_status(b.url, timeout=3.0)
            b.status = "active" if is_ok else "broken"
            b.status_code = code
        self._save_data()
        self._refresh_table()
        QMessageBox.information(None, "Verificação Concluída", "Status de todos os links foi atualizado com sucesso!")

    def _on_import_html(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Importar Favoritos do Navegador", "", "HTML (*.html *.htm)")
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                imported = import_netscape_bookmarks_html(content)
                self.bookmarks.extend(imported)
                self._save_data()
                self._update_tags_combo()
                self._refresh_table()
                QMessageBox.information(None, "Sucesso", f"{len(imported)} favoritos importados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao importar favoritos:\n{e}")

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Exportar Favoritos", "favoritos.html", "HTML (*.html);;JSON (*.json)")
        if path:
            try:
                if path.endswith(".json"):
                    save_bookmarks_json(self.bookmarks, Path(path))
                else:
                    html_str = export_netscape_bookmarks_html(self.bookmarks)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(html_str)
                QMessageBox.information(None, "Sucesso", "Favoritos exportados com sucesso!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar:\n{e}")
