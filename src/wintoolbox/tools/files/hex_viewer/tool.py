"""
Interface gráfica Fluent para o Visualizador Hexadecimal de Arquivos.
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.hex_viewer.logic import (
    format_hex_dump,
    read_hex_chunk,
    search_in_binary_file,
)


@register
class FilesHexViewerTool(Tool):
    id = "files.hex_viewer"
    name = "Visualizador Hexadecimal"
    description = "Visualizador hexadecimal (Hex Viewer): inspeciona bytes brutos de qualquer arquivo com visualização lado a lado em Hex/ASCII, offsets e busca binária."
    category = "Arquivos e Pastas"
    icon = "Code"
    tags = ["hex", "dump", "binario", "offset", "bytes", "visualizador"]

    PAGE_SIZE = 4096  # 256 linhas de 16 bytes

    def __init__(self) -> None:
        super().__init__()
        self._current_file: Optional[str] = None
        self._current_offset = 0
        self._total_size = 0

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Arquivo e Navegação
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_open = QPushButton("Abrir Arquivo...")
        btn_open.setStyleSheet("font-weight: bold;")
        self.lbl_file_info = QLabel("Nenhum arquivo aberto")
        self.lbl_file_info.setStyleSheet("color: #888888; font-style: italic;")

        btn_prev = QPushButton("◀ Página Anterior")
        btn_next = QPushButton("Próxima Página ▶")

        top_bar.addWidget(btn_open)
        top_bar.addWidget(self.lbl_file_info, 1)
        top_bar.addWidget(btn_prev)
        top_bar.addWidget(btn_next)

        layout.addLayout(top_bar)

        # Barra de Busca e Salto por Offset
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        search_bar.addWidget(QLabel("Ir para Offset:"))
        self.edit_offset = QLineEdit()
        self.edit_offset.setPlaceholderText("ex: 0x1000 ou 4096")
        self.edit_offset.setMaximumWidth(140)
        btn_goto = QPushButton("Ir")

        search_bar.addWidget(self.edit_offset)
        search_bar.addWidget(btn_goto)
        search_bar.addSpacing(16)

        search_bar.addWidget(QLabel("Buscar:"))
        self.edit_query = QLineEdit()
        self.edit_query.setPlaceholderText("Texto ASCII ou sequência Hex (ex: 89 50 4E)...")
        search_bar.addWidget(self.edit_query, 1)

        self.chk_hex_search = QCheckBox("Modo Hexadecimal")
        btn_search = QPushButton("Buscar")

        search_bar.addWidget(self.chk_hex_search)
        search_bar.addWidget(btn_search)

        layout.addLayout(search_bar)

        self.lbl_status = QLabel("Abra um arquivo binário para inspecionar os bytes.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Editor de Exibição Hex Dump
        self.text_dump = QPlainTextEdit()
        self.text_dump.setReadOnly(True)
        font = QFont("Consolas, Courier New, monospace", 10)
        self.text_dump.setFont(font)
        self.text_dump.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_dump, 1)

        # Conexões
        btn_open.clicked.connect(self._on_open_file)
        btn_prev.clicked.connect(self._on_prev_page)
        btn_next.clicked.connect(self._on_next_page)
        btn_goto.clicked.connect(self._on_goto_offset)
        btn_search.clicked.connect(self._on_search)

        return container

    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(None, "Abrir Arquivo para Leitura Hexadecimal", "", "Todos os Arquivos (*.*)")
        if not file_path:
            return

        self._current_file = file_path
        self._current_offset = 0
        p = Path(file_path)
        self.lbl_file_info.setText(f"{p.name} ({p.stat().st_size:,} bytes)")
        self._load_current_page()

    def _load_current_page(self) -> None:
        if not self._current_file:
            return

        try:
            data, real_off, total = read_hex_chunk(self._current_file, self._current_offset, self.PAGE_SIZE)
            self._current_offset = real_off
            self._total_size = total

            dump_text = format_hex_dump(data, base_offset=real_off)
            self.text_dump.setPlainText(dump_text)

            end_off = min(real_off + len(data), total)
            self.lbl_status.setText(
                f"Exibindo bytes 0x{real_off:08X} até 0x{end_off:08X} de {total:,} bytes "
                f"({real_off / (total or 1) * 100:.1f}% do arquivo)."
            )
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Ler", f"Falha ao ler arquivo:\n{exc}")

    def _on_prev_page(self) -> None:
        self._current_offset = max(0, self._current_offset - self.PAGE_SIZE)
        self._load_current_page()

    def _on_next_page(self) -> None:
        if self._current_offset + self.PAGE_SIZE < self._total_size:
            self._current_offset += self.PAGE_SIZE
            self._load_current_page()

    def _on_goto_offset(self) -> None:
        raw = self.edit_offset.text().strip()
        if not raw:
            return

        try:
            if raw.lower().startswith("0x"):
                target = int(raw, 16)
            else:
                target = int(raw)
            self._current_offset = target
            self._load_current_page()
        except ValueError:
            QMessageBox.warning(None, "Offset Inválido", "Digite um número decimal ou hexadecimal válido (ex: 0x1000 ou 4096).")

    def _on_search(self) -> None:
        if not self._current_file:
            return

        query = self.edit_query.text().strip()
        if not query:
            return

        is_hex = self.chk_hex_search.isChecked()
        matches = search_in_binary_file(self._current_file, query, is_hex=is_hex, max_results=10)

        if not matches:
            QMessageBox.information(None, "Busca Hexadecimal", f"Nenhuma ocorrência de '{query}' encontrada.")
            return

        first_match = matches[0]
        self._current_offset = (first_match // 16) * 16  # Alinha na linha de 16 bytes
        self._load_current_page()
        self.lbl_status.setText(f"Encontrada ocorrência no offset 0x{first_match:08X} ({first_match} bytes). Total de ocorrências: {len(matches)}.")
