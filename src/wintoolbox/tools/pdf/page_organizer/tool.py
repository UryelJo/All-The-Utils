"""
Interface gráfica do Organizador Visual de Páginas PDF.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QTransform
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.page_organizer.logic import (
    render_page_thumbnails, save_organized_pdf
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("pdf.page_organizer.ui")


class PageCardWidget(QFrame):
    """Card de miniatura individual para reordenar, girar ou excluir uma página."""

    def __init__(
        self,
        original_index: int,
        raw_png_bytes: bytes,
        parent_view: "PageOrganizerView",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.original_index = original_index
        self.raw_png_bytes = raw_png_bytes
        self.parent_view = parent_view
        self.rotation = 0
        self.is_deleted = False

        self.setFixedSize(180, 260)
        self.setObjectName("Card")
        self.setStyleSheet("""
            PageCardWidget {
                border: 1px solid #333333;
                border-radius: 8px;
                background-color: #202020;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Cabeçalho do Card
        self.lbl_title = QLabel(f"Página {original_index + 1}")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Imagem da miniatura
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setStyleSheet("background-color: #151515; border-radius: 4px;")
        layout.addWidget(self.lbl_thumb, stretch=1)

        self._base_pixmap = QPixmap()
        self._base_pixmap.loadFromData(raw_png_bytes)
        self._update_thumbnail_view()

        # Botões de Controle
        ctrl_lay = QHBoxLayout()
        ctrl_lay.setSpacing(4)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)

        self.btn_left = QPushButton("<")
        self.btn_left.setToolTip("Mover para esquerda")
        self.btn_left.setFixedSize(28, 24)
        self.btn_left.clicked.connect(lambda: self.parent_view.move_page(self, -1))
        ctrl_lay.addWidget(self.btn_left)

        self.btn_rotate = QPushButton("Girar")
        self.btn_rotate.setToolTip("Girar 90 graus no sentido horário")
        self.btn_rotate.setFixedHeight(24)
        self.btn_rotate.clicked.connect(self._rotate_90)
        ctrl_lay.addWidget(self.btn_rotate, stretch=1)

        self.btn_right = QPushButton(">")
        self.btn_right.setToolTip("Mover para direita")
        self.btn_right.setFixedSize(28, 24)
        self.btn_right.clicked.connect(lambda: self.parent_view.move_page(self, 1))
        ctrl_lay.addWidget(self.btn_right)

        layout.addLayout(ctrl_lay)

        # Botão Excluir / Restaurar
        self.btn_del = QPushButton("Excluir")
        self.btn_del.setFixedHeight(22)
        self.btn_del.setStyleSheet("font-size: 11px;")
        self.btn_del.clicked.connect(self._toggle_delete)
        layout.addWidget(self.btn_del)

    def _rotate_90(self) -> None:
        self.rotation = (self.rotation + 90) % 360
        rot_text = f" ({self.rotation}°)" if self.rotation != 0 else ""
        self.lbl_title.setText(f"Página {self.original_index + 1}{rot_text}")
        self._update_thumbnail_view()

    def _toggle_delete(self) -> None:
        self.is_deleted = not self.is_deleted
        if self.is_deleted:
            self.setStyleSheet("""
                PageCardWidget {
                    border: 1px dashed #d83b01;
                    border-radius: 8px;
                    background-color: #2d1e1e;
                    opacity: 0.6;
                }
            """)
            self.btn_del.setText("Restaurar")
            self.lbl_title.setText(f"Página {self.original_index + 1} (Excluída)")
            self.lbl_title.setStyleSheet("color: #d83b01; font-weight: 600; font-size: 11px;")
        else:
            self.setStyleSheet("""
                PageCardWidget {
                    border: 1px solid #333333;
                    border-radius: 8px;
                    background-color: #202020;
                }
            """)
            self.btn_del.setText("Excluir")
            rot_text = f" ({self.rotation}°)" if self.rotation != 0 else ""
            self.lbl_title.setText(f"Página {self.original_index + 1}{rot_text}")
            self.lbl_title.setStyleSheet("font-weight: 600; font-size: 11px;")

    def _update_thumbnail_view(self) -> None:
        if self._base_pixmap.isNull():
            return
        pix = self._base_pixmap
        if self.rotation != 0:
            transform = QTransform().rotate(self.rotation)
            pix = pix.transformed(transform, Qt.SmoothTransformation)
        scaled = pix.scaled(150, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_thumb.setPixmap(scaled)


@register
class PageOrganizerTool(Tool):
    id = "pdf.page_organizer"
    name = "Organizador Visual de Páginas PDF"
    category = "PDF"
    description = "Organizador visual de páginas PDF: reordena páginas por arrastar e soltar, gira páginas na orientação correta e remove páginas indesejadas com miniaturas."
    keywords = ["pdf", "organizar", "paginas", "miniaturas", "girar", "reordenar", "excluir", "visual"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PageOrganizerView(self, parent)


class PageOrganizerView(QWidget):
    def __init__(self, tool: PageOrganizerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_pdf: Optional[Path] = None
        self._cards: List[PageCardWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        # Barra Superior de Seleção de PDF
        top_card = QFrame()
        top_card.setObjectName("Card")
        t_lay = QHBoxLayout(top_card)
        t_lay.setContentsMargins(14, 12, 14, 12)
        t_lay.setSpacing(10)

        t_lay.addWidget(QLabel("Arquivo PDF:"))
        self.txt_pdf = QLineEdit()
        self.txt_pdf.setReadOnly(True)
        self.txt_pdf.setPlaceholderText("Selecione um arquivo PDF para carregar as miniaturas...")
        t_lay.addWidget(self.txt_pdf, stretch=1)

        btn_browse = QPushButton("Selecionar PDF...")
        btn_browse.clicked.connect(self._browse_pdf)
        t_lay.addWidget(btn_browse)

        self.btn_save = QPushButton("Salvar PDF Organizado...")
        self.btn_save.setProperty("class", "accent")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_organized)
        t_lay.addWidget(self.btn_save)

        layout.addWidget(top_card)

        # Status e Progresso
        self.lbl_status = QLabel("Nenhum documento carregado.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Área de Scroll com Grid de Miniaturas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(12)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, stretch=1)

    def _browse_pdf(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo PDF", "", "Arquivos PDF (*.pdf)")
        if not p:
            return
        self._current_pdf = Path(p)
        self.txt_pdf.setText(str(self._current_pdf))
        self._load_thumbnails_async()

    def _load_thumbnails_async(self) -> None:
        if not self._current_pdf:
            return

        self._clear_grid()
        self.btn_save.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # modo indeterminado
        self.lbl_status.setText("Renderizando miniaturas das páginas via motor PDFium...")

        pdf_path = self._current_pdf

        def _worker():
            return render_page_thumbnails(pdf_path, scale=0.25)

        def _on_done(thumbnails: List[tuple]):
            self.progress_bar.setVisible(False)
            self.lbl_status.setText(f"{len(thumbnails)} página(s) carregada(s). Arraste ou use os botões para organizar.")
            self._render_cards(thumbnails)
            self.btn_save.setEnabled(len(thumbnails) > 0)

        def _on_error(err):
            self.progress_bar.setVisible(False)
            self.lbl_status.setText(f"Erro ao carregar miniaturas: {err}")
            show_toast(self, f"Falha ao ler PDF: {err}", kind="error")

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _clear_grid(self) -> None:
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()

    def _render_cards(self, thumbnails: List[tuple]) -> None:
        self._clear_grid()
        columns = 5

        for idx, (orig_page, png_bytes) in enumerate(thumbnails):
            card = PageCardWidget(orig_page, png_bytes, self, self.scroll_content)
            self._cards.append(card)
            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)

    def move_page(self, card: PageCardWidget, direction: int) -> None:
        """Move o card para a esquerda (-1) ou para a direita (+1)."""
        if card not in self._cards:
            return
        idx = self._cards.index(card)
        new_idx = idx + direction
        if 0 <= new_idx < len(self._cards):
            self._cards.pop(idx)
            self._cards.insert(new_idx, card)
            self._relayout_grid()

    def _relayout_grid(self) -> None:
        columns = 5
        for i, card in enumerate(self._cards):
            self.grid_layout.removeWidget(card)
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(card, row, col)

    def _save_organized(self) -> None:
        if not self._current_pdf or not self._cards:
            return

        plan = []
        for card in self._cards:
            if not card.is_deleted:
                plan.append({
                    "original_index": card.original_index,
                    "rotation": card.rotation,
                })

        if not plan:
            show_toast(self, "Todas as páginas foram marcadas como excluídas!", kind="error")
            return

        suggested = self._current_pdf.parent / f"{self._current_pdf.stem}_organizado.pdf"
        dst, _ = QFileDialog.getSaveFileName(self, "Salvar Novo Arquivo PDF", str(suggested), "Arquivos PDF (*.pdf)")
        if not dst:
            return

        dst_path = Path(dst)
        src_path = self._current_pdf

        def _worker():
            return save_organized_pdf(src_path, dst_path, plan)

        def _on_done(saved_file):
            show_toast(self, "PDF organizado salvo com sucesso!", kind="success")
            QMessageBox.information(
                self,
                "PDF Salvo com Sucesso",
                f"O arquivo organizado foi salvo em:\n{saved_file}\n\n"
                f"Páginas incluídas: {len(plan)}"
            )

        def _on_error(err):
            show_toast(self, f"Erro ao salvar PDF: {err}", kind="error")

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
