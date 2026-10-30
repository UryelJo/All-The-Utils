"""
Roteador Inteligente de Arquivos e Pastas (Smart Drop Router & Dialog).
Analisa os arquivos/pastas soltos pelo usuário e sugere instantaneamente
todas as ferramentas compatíveis do catálogo.
"""
from pathlib import Path
from typing import List, Optional, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import BaseTool, FileTool, get_all_tools, get_tool
from wintoolbox.ui.icons import get_category_icon, get_glyph, get_icon_font
from wintoolbox.ui.theme import get_current_tokens

EXTRA_EXTENSION_MAPPING = {
    ".pdf": ["pdf.compress", "pdf.split_merge", "pdf.rotate", "pdf.extract", "pdf.security"],
    ".png": ["images.convert", "images.compress", "images.resize", "images.remove_bg", "images.ocr", "pdf.images_to_pdf"],
    ".jpg": ["images.convert", "images.compress", "images.resize", "images.exif", "images.ocr", "pdf.images_to_pdf"],
    ".jpeg": ["images.convert", "images.compress", "images.resize", "images.exif", "images.ocr", "pdf.images_to_pdf"],
    ".webp": ["images.convert", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".heic": ["images.convert", "images.exif", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".hif": ["images.convert", "images.exif", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".jfif": ["images.convert", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".psd": ["images.convert", "images.resize", "pdf.images_to_pdf"],
    ".qoi": ["images.convert", "images.resize", "pdf.images_to_pdf"],
    ".tga": ["images.convert", "images.resize", "pdf.images_to_pdf"],
    ".dds": ["images.convert", "images.resize"],
    ".jp2": ["images.convert", "images.resize", "pdf.images_to_pdf"],
    ".icns": ["images.convert", "images.favicon"],
    ".heif": ["images.convert", "images.exif", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".avif": ["images.convert", "images.compress", "images.resize", "pdf.images_to_pdf"],
    ".gif": ["images.gif_tools", "images.convert"],
    ".mp4": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".mov": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".m4v": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".webm": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".avi": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".wmv": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".ts": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".mts": ["media.convert", "media.frame_extractor", "media.inspector"],
    ".m2ts": ["media.convert", "media.frame_extractor", "media.inspector"],
    ".3gp": ["media.convert", "media.frame_extractor"],
    ".vob": ["media.convert", "media.inspector"],
    ".opus": ["media.convert", "media.normalize", "media.inspector"],
    ".flac": ["media.convert", "media.normalize", "media.player"],
    ".m4a": ["media.convert", "media.normalize", "media.player"],
    ".ogg": ["media.convert", "media.normalize", "media.player"],
    ".aiff": ["media.convert", "media.normalize"],
    ".ac3": ["media.convert", "media.inspector"],
    ".mkv": ["media.convert", "media.trim_merge", "media.frame_extractor", "media.player"],
    ".mp3": ["media.convert", "media.trim_merge", "media.id3_editor", "media.player"],
    ".wav": ["media.convert", "media.trim_merge", "media.player"],
    ".zip": ["archive.manager"],
    ".7z": ["archive.manager"],
    ".rar": ["archive.manager"],
    ".tar": ["archive.manager"],
    ".gz": ["archive.manager"],
    ".md": ["data.doc_converter"],
    ".json": ["data.converter", "data.beautifier"],
    ".xml": ["data.converter", "data.beautifier"],
    ".csv": ["data.converter"],
    ".yaml": ["data.converter"],
    ".yml": ["data.converter"],
}

FOLDER_RECOMMENDED_TOOLS = [
    "images.convert",
    "files.auto_organize",
    "files.rename",
    "files.duplicates",
    "files.disk_usage",
    "files.search",
    "files.backup",
    "archive.manager",
]

UNIVERSAL_FILE_TOOLS = [
    "encode.crypto_hash",
    "files.encrypt",
    "files.timestamp_editor",
    "files.lock_checker",
    "files.split_merge",
]


def find_compatible_tools_for_paths(paths: List[Path]) -> List[BaseTool]:
    """
    Descobre e ordena por relevância todas as ferramentas compatíveis com os arquivos/pastas informados.
    """
    if not paths:
        return []

    has_dirs = any(p.is_dir() for p in paths)
    exts: Set[str] = set()
    for p in paths:
        if p.is_file() and p.suffix:
            exts.add(p.suffix.lower())
        elif p.is_dir():
            # Amostra rápida dos primeiros arquivos da pasta para detectar extensões
            try:
                count = 0
                for child in p.iterdir():
                    if child.is_file() and child.suffix:
                        exts.add(child.suffix.lower())
                        count += 1
                        if count >= 25:
                            break
            except Exception:
                pass

    ordered_ids: List[str] = []

    def _add_id(tid: str) -> None:
        if tid not in ordered_ids and get_tool(tid) is not None:
            ordered_ids.append(tid)

    # 1. Mapeamento prioritário por extensão
    for ext in sorted(exts):
        for tid in EXTRA_EXTENSION_MAPPING.get(ext, []):
            _add_id(tid)

    # 2. Todas as FileTools cujo 'accepts' contém alguma das extensões
    for tool in get_all_tools():
        if isinstance(tool, FileTool) and tool.accepts:
            accepted = {e.lower() for e in tool.accepts}
            if exts & accepted:
                _add_id(tool.id)

    # 3. Se houver diretórios, inclui ferramentas de organização e análise de pastas
    if has_dirs:
        for tid in FOLDER_RECOMMENDED_TOOLS:
            _add_id(tid)

    # 4. Ferramentas universais de arquivos
    for tid in UNIVERSAL_FILE_TOOLS:
        _add_id(tid)

    return [get_tool(tid) for tid in ordered_ids if get_tool(tid) is not None]


class SmartDropDialog(QDialog):
    """Modal rápido que apresenta as ferramentas compatíveis com os itens soltos."""
    tool_chosen = Signal(str, list)  # (tool_id, List[Path])

    def __init__(self, paths: List[Path], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.paths = paths
        self.compatible_tools = find_compatible_tools_for_paths(paths)
        self.setWindowTitle("Selecionar Ferramenta para os Itens")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(540, 400)

        self._build_ui()

    def _build_ui(self) -> None:
        t = get_current_tokens()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame(self)
        container.setObjectName("commandPaletteContainer")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(18, 16, 18, 16)
        c_layout.setSpacing(10)

        # Cabeçalho
        hdr = QHBoxLayout()
        count = len(self.paths)
        summary = f"{count} item(ns) detectado(s) - Escolha o que deseja fazer:"
        lbl_title = QLabel(summary)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 14px;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_close = QPushButton("Fechar")
        btn_close.setProperty("class", "ghost")
        btn_close.clicked.connect(self.reject)
        hdr.addWidget(btn_close)
        c_layout.addLayout(hdr)

        # Resumo dos nomes dos arquivos
        names_preview = ", ".join(p.name for p in self.paths[:3])
        if len(self.paths) > 3:
            names_preview += f" (+{len(self.paths) - 3})"
        lbl_files = QLabel(f"Selecionados: {names_preview}")
        lbl_files.setProperty("class", "secondary")
        c_layout.addWidget(lbl_files)

        # Lista de ferramentas compatíveis
        self.list_tools = QListWidget()
        self.list_tools.itemActivated.connect(self._on_activated)
        self.list_tools.itemClicked.connect(self._on_activated)
        c_layout.addWidget(self.list_tools, stretch=1)

        for tool in self.compatible_tools:
            kind_str = "Processamento em Lote" if isinstance(tool, FileTool) else "Painel Interativo"
            item = QListWidgetItem(
                get_category_icon(tool.category, size=18),
                f"{tool.name}  •  {tool.category} ({kind_str})\n{tool.description}"
            )
            item.setData(Qt.UserRole, tool.id)
            self.list_tools.addItem(item)

        if self.list_tools.count() > 0:
            self.list_tools.setCurrentRow(0)

        # Rodapé
        footer = QHBoxLayout()
        lbl_hint = QLabel("Clique em uma ferramenta ou pressione Enter para abrir")
        lbl_hint.setProperty("class", "muted")
        footer.addWidget(lbl_hint)
        footer.addStretch()

        btn_open = QPushButton("Abrir Ferramenta Selecionada")
        btn_open.setProperty("class", "primary")
        btn_open.clicked.connect(self._open_current)
        footer.addWidget(btn_open)
        c_layout.addLayout(footer)

        root.addWidget(container)

    def _open_current(self) -> None:
        curr = self.list_tools.currentItem()
        if curr:
            self._on_activated(curr)

    def _on_activated(self, item: QListWidgetItem) -> None:
        tid = item.data(Qt.UserRole)
        if tid:
            self.tool_chosen.emit(str(tid), self.paths)
            self.accept()
