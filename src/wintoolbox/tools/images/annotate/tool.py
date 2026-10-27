"""
Interface gráfica do Editor de Anotações sobre Imagens.
"""
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QMessageBox, QPushButton, QRadioButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.annotate.logic import (
    AnnotationItem, render_annotations
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("images.annotate.ui")

COLOR_PALETTE = [
    ("#EF4444", "Vermelho"),
    ("#F59E0B", "Laranja"),
    ("#10B981", "Verde"),
    ("#3B82F6", "Azul"),
    ("#8B5CF6", "Roxo"),
    ("#FFFFFF", "Branco"),
    ("#111827", "Preto"),
]


class CanvasWidget(QWidget):
    """Widget de pintura interativa sobre a imagem."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pil_base_image: Optional[Image.Image] = None
        self.cached_pixmap: Optional[QPixmap] = None
        self.annotations: List[AnnotationItem] = []

        # Estado atual do desenho
        self.current_tool: str = "arrow"
        self.current_color: str = "#EF4444"
        self.current_width: int = 4
        self.step_counter: int = 1

        self._start_pt: Optional[QPoint] = None
        self._current_pt: Optional[QPoint] = None
        self._is_drawing: bool = False
        self.setMouseTracking(True)

    def set_base_image(self, img: Image.Image) -> None:
        self.pil_base_image = img.convert("RGBA")
        self.annotations.clear()
        self.step_counter = 1
        self._render_cache()
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        if self.cached_pixmap:
            return self.cached_pixmap.size()
        return super().sizeHint()

    def _render_cache(self) -> None:
        if not self.pil_base_image:
            self.cached_pixmap = None
            return

        rendered_pil = render_annotations(self.pil_base_image, self.annotations)
        data = rendered_pil.tobytes("raw", "RGBA")
        qimg = QImage(data, rendered_pil.width, rendered_pil.height, QImage.Format_RGBA8888)
        self.cached_pixmap = QPixmap.fromImage(qimg)
        self.setFixedSize(rendered_pil.width, rendered_pil.height)

    def undo_last(self) -> None:
        if self.annotations:
            removed = self.annotations.pop()
            if removed.tool_type == "step" and self.step_counter > 1:
                self.step_counter -= 1
            self._render_cache()
            self.update()

    def clear_all(self) -> None:
        if self.annotations:
            self.annotations.clear()
            self.step_counter = 1
            self._render_cache()
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pil_base_image:
            self._start_pt = event.position().toPoint()
            self._current_pt = self._start_pt
            self._is_drawing = True

            # Se for clique único de passo numerado
            if self.current_tool == "step":
                x, y = self._start_pt.x(), self._start_pt.y()
                ann = AnnotationItem(
                    tool_type="step",
                    coords=(x, y, x, y),
                    color=self.current_color,
                    width=self.current_width,
                    step_num=self.step_counter
                )
                self.step_counter += 1
                self.annotations.append(ann)
                self._is_drawing = False
                self._render_cache()
                self.update()

    def mouseMoveEvent(self, event):
        if self._is_drawing:
            self._current_pt = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_drawing:
            self._is_drawing = False
            p1 = self._start_pt
            p2 = event.position().toPoint()

            if p1 and p2:
                x1, y1 = p1.x(), p1.y()
                x2, y2 = p2.x(), p2.y()

                if self.current_tool == "text":
                    text, ok = QInputDialog.getText(self, "Texto de Anotação", "Digite o texto para inserir:")
                    if ok and text.strip():
                        ann = AnnotationItem(
                            tool_type="text",
                            coords=(x1, y1, x2, y2),
                            color=self.current_color,
                            width=self.current_width,
                            text=text.strip()
                        )
                        self.annotations.append(ann)
                elif self.current_tool in ("arrow", "rect", "blur", "pixelate"):
                    # Garante que houve um arrasto mínimo
                    if abs(x2 - x1) > 3 or abs(y2 - y1) > 3:
                        ann = AnnotationItem(
                            tool_type=self.current_tool,
                            coords=(x1, y1, x2, y2),
                            color=self.current_color,
                            width=self.current_width
                        )
                        self.annotations.append(ann)

                self._render_cache()
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.cached_pixmap:
            painter.drawPixmap(0, 0, self.cached_pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#1a1a1a"))
            painter.setPen(QPen(QColor(255, 255, 255, 70)))
            painter.drawText(self.rect(), Qt.AlignCenter, "Abra ou arraste uma imagem aqui para começar a anotar")

        # Desenha prévia interativa enquanto arrasta
        if self._is_drawing and self._start_pt and self._current_pt:
            p1 = self._start_pt
            p2 = self._current_pt
            pen = QPen(QColor(self.current_color), self.current_width, Qt.DashLine)
            painter.setPen(pen)

            if self.current_tool == "arrow":
                painter.drawLine(p1, p2)
            elif self.current_tool in ("rect", "blur", "pixelate", "text"):
                r = QRect(p1, p2).normalized()
                painter.drawRect(r)


@register
class AnnotateTool(Tool):
    id = "images.annotate"
    name = "Editor de Anotações"
    category = "Imagens e Mídia"
    description = "Anotações sobre imagens com setas, retângulos, numeração de passos, textos e tarjas de desfoque ou pixelização"
    keywords = ["anotação", "anotar", "seta", "retângulo", "passos", "censura", "desfoque", "pixelizar", "privacidade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return AnnotateView(self, parent)


class AnnotateView(QWidget):
    def __init__(self, tool: AnnotateTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._current_path: Optional[Path] = None

        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        root.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Painel de Ferramentas
        toolbar_card = QFrame()
        toolbar_card.setObjectName("Card")
        t_lay = QHBoxLayout(toolbar_card)
        t_lay.setContentsMargins(12, 8, 12, 8)
        t_lay.setSpacing(10)

        self.btn_open = QPushButton("Abrir Imagem...")
        self.btn_open.setProperty("accent", True)
        self.btn_open.clicked.connect(self._open_file_dialog)
        t_lay.addWidget(self.btn_open)

        # Modos de ferramenta
        t_lay.addWidget(QLabel("Ferramenta:"))
        self.tool_group = QButtonGroup(self)

        tools = [
            ("arrow", "Seta"),
            ("rect", "Retângulo"),
            ("step", "Passo (1, 2, 3)"),
            ("text", "Texto"),
            ("pixelate", "Pixelizar"),
            ("blur", "Desfocar"),
        ]

        for i, (tid, label) in enumerate(tools):
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            self.tool_group.addButton(rb, i)
            t_lay.addWidget(rb)
            # Armazena id no radio button
            rb.setProperty("tool_id", tid)

        self.tool_group.buttonClicked.connect(self._on_tool_selected)

        # Espessura
        t_lay.addWidget(QLabel("Espessura:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(2, 20)
        self.spin_width.setValue(4)
        self.spin_width.valueChanged.connect(self._on_width_changed)
        t_lay.addWidget(self.spin_width)

        # Seletor de cores
        t_lay.addWidget(QLabel("Cor:"))
        self.cmb_color = QComboBox()
        for hex_code, name in COLOR_PALETTE:
            self.cmb_color.addItem(name, hex_code)
        self.cmb_color.currentIndexChanged.connect(self._on_color_changed)
        t_lay.addWidget(self.cmb_color)

        t_lay.addStretch(1)

        # Botões de ação rápida
        self.btn_undo = QPushButton("Desfazer")
        self.btn_undo.clicked.connect(self._undo)
        t_lay.addWidget(self.btn_undo)

        self.btn_clear = QPushButton("Limpar Tudo")
        self.btn_clear.clicked.connect(self._clear)
        t_lay.addWidget(self.btn_clear)

        root.addWidget(toolbar_card)

        # Scroll Area com Canvas de Desenho
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("background-color: #121212; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;")

        self.canvas = CanvasWidget()
        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll, stretch=1)

        # Barra Inferior
        bot_card = QFrame()
        bot_card.setObjectName("Card")
        b_lay = QHBoxLayout(bot_card)
        b_lay.setContentsMargins(14, 10, 14, 10)
        b_lay.setSpacing(10)

        self.lbl_info = QLabel("Abra uma foto ou cole da área de transferência.")
        self.lbl_info.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 11px;")
        b_lay.addWidget(self.lbl_info)

        b_lay.addStretch(1)

        self.btn_copy = QPushButton("Copiar com Anotações")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        b_lay.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Salvar Imagem...")
        self.btn_save.setEnabled(False)
        self.btn_save.setProperty("accent", True)
        self.btn_save.clicked.connect(self._save_image)
        b_lay.addWidget(self.btn_save)

        root.addWidget(bot_card)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para Anotar",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;Todos os Arquivos (*.*)"
        )
        if path:
            self.load_image(Path(path))

    def load_image(self, path: Path) -> None:
        try:
            self._current_path = path
            with Image.open(path) as img:
                from PIL import ImageOps
                loaded = ImageOps.exif_transpose(img.copy())

            self.canvas.set_base_image(loaded)
            self.lbl_info.setText(f"{path.name}  •  {loaded.width} × {loaded.height} px")
            self.btn_copy.setEnabled(True)
            self.btn_save.setEnabled(True)
            show_toast(self, f"Imagem carregada: {path.name}", duration_ms=2500)
        except Exception as e:
            _log.error(f"Erro ao carregar imagem: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo:\n{e}")

    def _on_tool_selected(self, button) -> None:
        tid = button.property("tool_id")
        if tid:
            self.canvas.current_tool = tid

    def _on_color_changed(self) -> None:
        hex_code = self.cmb_color.currentData()
        if hex_code:
            self.canvas.current_color = hex_code

    def _on_width_changed(self, val: int) -> None:
        self.canvas.current_width = val

    def _undo(self) -> None:
        self.canvas.undo_last()

    def _clear(self) -> None:
        self.canvas.clear_all()

    def _copy_to_clipboard(self) -> None:
        if not self.canvas.cached_pixmap:
            return
        QApplication.clipboard().setPixmap(self.canvas.cached_pixmap)
        show_toast(self, "Imagem com anotações copiada para a área de transferência!", duration_ms=2500)

    def _save_image(self) -> None:
        if not self.canvas.pil_base_image:
            return

        suggested = self._current_path.with_stem(self._current_path.stem + "_anotada") if self._current_path else Path("imagem_anotada.png")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Imagem Anotada",
            str(suggested),
            "Imagem PNG (*.png);;Imagem JPEG (*.jpg);;Imagem WebP (*.webp)"
        )
        if not save_path:
            return

        final_img = render_annotations(self.canvas.pil_base_image, self.canvas.annotations)
        target = Path(save_path)
        if target.suffix.lower() in (".jpg", ".jpeg"):
            final_img.convert("RGB").save(target, format="JPEG", quality=95)
        else:
            final_img.save(target)

        show_toast(self, f"Salvo com sucesso em {target.name}!", duration_ms=3000)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
                self.load_image(p)
                break
