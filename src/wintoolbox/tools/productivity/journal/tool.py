"""
Interface de usuário para o Diário Pessoal com calendário e exportação Markdown.
"""
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.settings import get_settings_dir
from wintoolbox.tools.productivity.journal.logic import (
    JournalEntry,
    export_journal_to_markdown,
    filter_entries,
    get_entry_by_date,
    load_journal,
    save_journal,
)


@register
class JournalTool(Tool):
    """Diário de registros pessoais com navegação por calendário e exportação Markdown."""

    id = "productivity.journal"
    name = "Diário Pessoal & Registros Diários"
    description = "Registre reflexões, memórias e progresso diário com calendário, categorização de humor e exportação Markdown."
    category = "productivity"

    def __init__(self):
        super().__init__()
        self.storage_path = get_settings_dir() / "journal_entries.json"
        self.entries: List[JournalEntry] = load_journal(self.storage_path)
        self.selected_date: str = date.today().isoformat()

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Diário Pessoal & Registros Diários")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Seus pensamentos e registros guardados 100% no seu computador com exportação estruturada em Markdown."
        )
        desc.setStyleSheet("color: #888888;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        top_bar.addLayout(title_box, 1)

        btn_export = QPushButton("Exportar Diário (.md)")
        btn_export.setStyleSheet("font-weight: bold; background-color: #0284c7; color: white; padding: 6px 14px;")
        btn_export.clicked.connect(self._on_export_markdown)
        top_bar.addWidget(btn_export)

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lado Esquerdo: Calendário e Histórico
        left_box = QWidget()
        v_left = QVBoxLayout(left_box)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(8)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_calendar_date_changed)
        v_left.addWidget(self.calendar)

        v_left.addWidget(QLabel("<b>Histórico de Registros:</b>"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar no diário...")
        self.txt_search.textChanged.connect(self._refresh_history_list)
        v_left.addWidget(self.txt_search)

        self.list_history = QListWidget()
        self.list_history.itemClicked.connect(self._on_history_item_clicked)
        v_left.addWidget(self.list_history, 1)

        splitter.addWidget(left_box)

        # Lado Direito: Editor de Registro
        right_box = QWidget()
        v_right = QVBoxLayout(right_box)
        v_right.setContentsMargins(10, 0, 0, 0)
        v_right.setSpacing(10)

        self.lbl_entry_date = QLabel(f"Registro do dia: {self.selected_date}")
        self.lbl_entry_date.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284c7;")
        v_right.addWidget(self.lbl_entry_date)

        form = QFormLayout()
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Título do dia ou assunto principal")
        form.addRow("Título:", self.txt_title)

        mood_tags_box = QHBoxLayout()
        self.cmb_mood = QComboBox()
        self.cmb_mood.addItems([
            "😊 Produtivo", "⚡ Energizado", "🌟 Inspirado", "😐 Neutro", "🤔 Reflexivo", "😴 Cansado", "😟 Ansioso"
        ])
        mood_tags_box.addWidget(self.cmb_mood, 1)

        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("Tags (ex: Ideias, Treino, Livros)")
        mood_tags_box.addWidget(self.txt_tags, 2)
        form.addRow("Humor & Tags:", mood_tags_box)

        v_right.addLayout(form)

        v_right.addWidget(QLabel("<b>Texto do Diário (Markdown):</b>"))
        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("Escreva aqui suas ideias, memórias e planos para hoje...")
        v_right.addWidget(self.txt_content, 1)

        # Barra de Ações do Diário
        act_box = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #16a34a; font-weight: bold;")
        act_box.addWidget(self.lbl_status)
        act_box.addStretch()

        self.btn_delete = QPushButton("Excluir Entrada")
        self.btn_delete.setStyleSheet("color: #dc2626;")
        self.btn_delete.clicked.connect(self._on_delete_entry)
        act_box.addWidget(self.btn_delete)

        self.btn_save = QPushButton("Salvar Registro")
        self.btn_save.setStyleSheet("font-weight: bold; background-color: #16a34a; color: white; padding: 6px 16px;")
        self.btn_save.clicked.connect(self._on_save_entry)
        act_box.addWidget(self.btn_save)

        v_right.addLayout(act_box)

        splitter.addWidget(right_box)
        splitter.setSizes([340, 560])
        layout.addWidget(splitter, 1)

        self._refresh_history_list()
        self._load_entry_for_selected_date()
        return widget

    def _save_data(self) -> None:
        save_journal(self.entries, self.storage_path)

    def _refresh_history_list(self) -> None:
        q = self.txt_search.text()
        filtered = filter_entries(self.entries, query=q)

        self.list_history.clear()
        for e in filtered:
            item = QListWidgetItem(f"[{e.date}] {e.title}")
            item.setData(Qt.ItemDataRole.UserRole, e.date)
            self.list_history.addItem(item)

    def _on_calendar_date_changed(self) -> None:
        qdt = self.calendar.selectedDate()
        self.selected_date = qdt.toString("yyyy-MM-dd")
        self.lbl_entry_date.setText(f"Registro do dia: {self.selected_date}")
        self._load_entry_for_selected_date()

    def _on_history_item_clicked(self, item: QListWidgetItem) -> None:
        dt_str = item.data(Qt.ItemDataRole.UserRole)
        if dt_str:
            self.selected_date = dt_str
            qdt = QDate.fromString(dt_str, "yyyy-MM-dd")
            self.calendar.setSelectedDate(qdt)
            self.lbl_entry_date.setText(f"Registro do dia: {self.selected_date}")
            self._load_entry_for_selected_date()

    def _load_entry_for_selected_date(self) -> None:
        self.lbl_status.clear()
        entry = get_entry_by_date(self.entries, self.selected_date)
        if entry:
            self.txt_title.setText(entry.title)
            idx = self.cmb_mood.findText(entry.mood)
            if idx >= 0:
                self.cmb_mood.setCurrentIndex(idx)
            self.txt_tags.setText(", ".join(entry.tags))
            self.txt_content.setPlainText(entry.content)
            self.btn_delete.setEnabled(True)
        else:
            self.txt_title.clear()
            self.txt_tags.clear()
            self.txt_content.clear()
            self.btn_delete.setEnabled(False)

    def _on_save_entry(self) -> None:
        title = self.txt_title.text().strip() or "Registro Diário"
        mood = self.cmb_mood.currentText()
        tags = [t.strip() for t in self.txt_tags.text().split(",") if t.strip()]
        content = self.txt_content.toPlainText()

        entry = get_entry_by_date(self.entries, self.selected_date)
        if entry:
            entry.title = title
            entry.mood = mood
            entry.tags = tags
            entry.content = content
        else:
            import uuid
            new_e = JournalEntry(
                id=str(uuid.uuid4()),
                date=self.selected_date,
                title=title,
                content=content,
                mood=mood,
                tags=tags
            )
            self.entries.append(new_e)

        self._save_data()
        self._refresh_history_list()
        self.btn_delete.setEnabled(True)
        self.lbl_status.setText("Registro salvo com sucesso!")

    def _on_delete_entry(self) -> None:
        entry = get_entry_by_date(self.entries, self.selected_date)
        if not entry:
            return
        reply = QMessageBox.question(
            None,
            "Excluir Registro",
            f"Deseja excluir o registro do dia {self.selected_date}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.entries = [e for e in self.entries if e.date != self.selected_date]
            self._save_data()
            self._refresh_history_list()
            self._load_entry_for_selected_date()

    def _on_export_markdown(self) -> None:
        path, _ = QFileDialog.getSaveFileName(None, "Exportar Diário em Markdown", "meu_diario.md", "Markdown (*.md)")
        if path:
            try:
                md_text = export_journal_to_markdown(self.entries)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md_text)
                QMessageBox.information(None, "Sucesso", "Diário exportado com sucesso em Markdown!")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao exportar diário:\n{e}")
