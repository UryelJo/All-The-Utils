"""
Interface gráfica do Editor de Anotações sobre Imagens.
Suporta ferramentas vetoriais, censura por desfoque/pixelização, seleção,
edição, arrasto de anotações e zoom interativo.
"""
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget
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
    ("#EC4899", "Rosa"),
    ("#FFFFFF", "Branco"),
    ("#111827", "Preto"),
]


class CanvasWidget(QWidget):
    """Widget de pintura e manipulação interativa sobre a imagem."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pil_base_image: Optional[Image.Image] = None
        self.cached_pixmap: Optional[QPixmap] = None
        self.annotations: List[AnnotationItem] = []
        self.selected_item: Optional[AnnotationItem] = None

        # Estado da ferramenta
        self.current_tool: str = "arrow"
        self.current_color: str = "#EF4444"
        self.current_width: int = 4
        self.arrow_style: str = "filled"
        self.line_style: str = "solid"
        self.step_format: str = "1,2,3"
        self.font_size: int = 24
        self.is_filled: bool = False
        self.step_counter: int = 1

        # Zoom
        self._zoom: float = 1.0

        # Rastreamento de mouse
        self._start_pt: Optional[QPoint] = None
        self._current_pt: Optional[QPoint] = None
        self._drag_start_coords: Optional[Tuple[int, int, int, int]] = None
        self._is_drawing: bool = False
        self._is_moving: bool = False

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_base_image(self, img: Image.Image) -> None:
        self.pil_base_image = img.convert("RGBA")
        self.annotations.clear()
        self.selected_item = None
        self.step_counter = 1
        self._zoom = 1.0
        self._render_cache()
        self._update_widget_size()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.1, min(5.0, zoom))
        self._update_widget_size()
        self.update()

    def get_zoom(self) -> float:
        return self._zoom

    def _update_widget_size(self) -> None:
        if self.pil_base_image:
            w = int(self.pil_base_image.width * self._zoom)
            h = int(self.pil_base_image.height * self._zoom)
            self.setFixedSize(w, h)
        else:
            self.setFixedSize(400, 300)
        self.updateGeometry()

    def _render_cache(self) -> None:
        if not self.pil_base_image:
            self.cached_pixmap = None
            return

        rendered_pil = render_annotations(self.pil_base_image, self.annotations, self.selected_item)
        data = rendered_pil.tobytes("raw", "RGBA")
        qimg = QImage(data, rendered_pil.width, rendered_pil.height, QImage.Format_RGBA8888)
        self.cached_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def _map_to_image_coords(self, pt: QPoint) -> Tuple[int, int]:
        """Converte coordenadas do widget para coordenadas da imagem considerando zoom."""
        if self._zoom <= 0:
            return pt.x(), pt.y()
        return int(pt.x() / self._zoom), int(pt.y() / self._zoom)

    def undo_last(self) -> None:
        if self.annotations:
            removed = self.annotations.pop()
            if removed is self.selected_item:
                self.selected_item = None
            if removed.tool_type == "step" and self.step_counter > 1:
                self.step_counter -= 1
            self._render_cache()

    def clear_all(self) -> None:
        if self.annotations:
            self.annotations.clear()
            self.selected_item = None
            self.step_counter = 1
            self._render_cache()

    def delete_selected(self) -> None:
        if self.selected_item and self.selected_item in self.annotations:
            self.annotations.remove(self.selected_item)
            self.selected_item = None
            self._render_cache()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.selected_item:
                self.delete_selected()
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pil_base_image:
            ix, iy = self._map_to_image_coords(event.position().toPoint())
            self._start_pt = QPoint(ix, iy)
            self._current_pt = self._start_pt

            if self.current_tool == "select":
                # Verifica clique em anotação existente (de trás para frente)
                hit_item = None
                for ann in reversed(self.annotations):
                    if ann.contains_point(ix, iy):
                        hit_item = ann
                        break

                self.selected_item = hit_item
                if self.selected_item:
                    self._is_moving = True
                    self._drag_start_coords = self.selected_item.coords
                self._render_cache()
                return

            # Clique de passo numerado
            if self.current_tool == "step":
                ann = AnnotationItem(
                    tool_type="step",
                    coords=(ix, iy, ix, iy),
                    color=self.current_color,
                    width=self.current_width,
                    step_num=self.step_counter,
                    step_format=self.step_format
                )
                self.step_counter += 1
                self.annotations.append(ann)
                self.selected_item = ann
                self._render_cache()
                return

            self._is_drawing = True

    def mouseMoveEvent(self, event):
        if not self.pil_base_image:
            return

        ix, iy = self._map_to_image_coords(event.position().toPoint())
        self._current_pt = QPoint(ix, iy)

        if self._is_moving and self.selected_item and self._start_pt and self._drag_start_coords:
            dx = ix - self._start_pt.x()
            dy = iy - self._start_pt.y()
            orig_x1, orig_y1, orig_x2, orig_y2 = self._drag_start_coords
            self.selected_item.coords = (orig_x1 + dx, orig_y1 + dy, orig_x2 + dx, orig_y2 + dy)
            self._render_cache()
            return

        if self._is_drawing:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.pil_base_image:
            ix, iy = self._map_to_image_coords(event.position().toPoint())

            if self._is_moving:
                self._is_moving = False
                self._drag_start_coords = None
                return

            if self._is_drawing and self._start_pt:
                self._is_drawing = False
                x1, y1 = self._start_pt.x(), self._start_pt.y()
                x2, y2 = ix, iy

                if self.current_tool == "text":
                    text, ok = QInputDialog.getText(self, "Texto de Anotação", "Digite o texto para inserir:")
                    if ok and text.strip():
                        ann = AnnotationItem(
                            tool_type="text",
                            coords=(x1, y1, x2, y2),
                            color=self.current_color,
                            width=self.current_width,
                            text=text.strip(),
                            font_size=self.font_size
                        )
                        self.annotations.append(ann)
                        self.selected_item = ann
                elif self.current_tool in ("arrow", "rect", "ellipse", "blur", "pixelate"):
                    if abs(x2 - x1) > 3 or abs(y2 - y1) > 3:
                        ann = AnnotationItem(
                            tool_type=self.current_tool,
                            coords=(x1, y1, x2, y2),
                            color=self.current_color,
                            width=self.current_width,
                            style=self.line_style,
                            arrow_style=self.arrow_style,
                            filled=self.is_filled
                        )
                        self.annotations.append(ann)
                        self.selected_item = ann

                self._render_cache()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.cached_pixmap:
            # Escala no pintor conforme o zoom aplicado
            painter.save()
            painter.scale(self._zoom, self._zoom)
            painter.drawPixmap(0, 0, self.cached_pixmap)

            # Desenha prévia interativa enquanto arrasta
            if self._is_drawing and self._start_pt and self._current_pt:
                p1 = self._start_pt
                p2 = self._current_pt
                pen_style = Qt.DashLine if self.line_style != "solid" else Qt.DashLine
                pen = QPen(QColor(self.current_color), self.current_width, pen_style)
                painter.setPen(pen)

                if self.current_tool == "arrow":
                    painter.drawLine(p1, p2)
                elif self.current_tool in ("rect", "blur", "pixelate", "text"):
                    r = QRect(p1, p2).normalized()
                    painter.drawRect(r)
                elif self.current_tool == "ellipse":
                    r = QRect(p1, p2).normalized()
                    painter.drawEllipse(r)

            painter.restore()
        else:
            painter.fillRect(self.rect(), QColor("#1a1a1a"))
            painter.setPen(QPen(QColor(255, 255, 255, 70)))
            painter.drawText(self.rect(), Qt.AlignCenter, "Abra ou arraste uma imagem aqui para começar a anotar")


@register
class AnnotateTool(Tool):
    id = "images.annotate"
    name = "Editor de Anotações"
    category = "Imagens"
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

        # Painel Superior: Ferramentas Principais
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
            ("select", "Selecionar / Mover"),
            ("arrow", "Seta"),
            ("rect", "Retângulo"),
            ("ellipse", "Círculo / Elipse"),
            ("step", "Passo"),
            ("text", "Texto"),
            ("pixelate", "Pixelizar"),
            ("blur", "Desfocar"),
        ]

        for i, (tid, label) in enumerate(tools):
            rb = QRadioButton(label)
            if tid == "arrow":
                rb.setChecked(True)
            self.tool_group.addButton(rb, i)
            t_lay.addWidget(rb)
            rb.setProperty("tool_id", tid)

        self.tool_group.buttonClicked.connect(self._on_tool_selected)

        t_lay.addStretch(1)

        # Controles de Zoom
        t_lay.addWidget(QLabel("Zoom:"))
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.clicked.connect(lambda: self._adjust_zoom(0.8))
        t_lay.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(42)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        t_lay.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.clicked.connect(lambda: self._adjust_zoom(1.25))
        t_lay.addWidget(self.btn_zoom_in)

        self.btn_zoom_reset = QPushButton("1:1")
        self.btn_zoom_reset.setFixedWidth(36)
        self.btn_zoom_reset.clicked.connect(lambda: self._set_zoom(1.0))
        t_lay.addWidget(self.btn_zoom_reset)

        self.btn_zoom_fit = QPushButton("Ajustar")
        self.btn_zoom_fit.clicked.connect(self._fit_zoom)
        t_lay.addWidget(self.btn_zoom_fit)

        root.addWidget(toolbar_card)

        # Painel Secundário: Opções de Estilo da Ferramenta
        style_card = QFrame()
        style_card.setObjectName("Card")
        s_lay = QHBoxLayout(style_card)
        s_lay.setContentsMargins(12, 6, 12, 6)
        s_lay.setSpacing(12)

        s_lay.addWidget(QLabel("Cor:"))
        self.cmb_color = QComboBox()
        for hex_code, name in COLOR_PALETTE:
            self.cmb_color.addItem(name, hex_code)
        self.cmb_color.currentIndexChanged.connect(self._on_color_changed)
        s_lay.addWidget(self.cmb_color)

        s_lay.addWidget(QLabel("Espessura:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 24)
        self.spin_width.setValue(4)
        self.spin_width.valueChanged.connect(self._on_width_changed)
        s_lay.addWidget(self.spin_width)

        # Seta: Estilo da ponta
        self.lbl_arrow_head = QLabel("Ponta:")
        s_lay.addWidget(self.lbl_arrow_head)
        self.cmb_arrow_style = QComboBox()
        self.cmb_arrow_style.addItem("Preenchida", "filled")
        self.cmb_arrow_style.addItem("Clássica", "classic")
        self.cmb_arrow_style.addItem("Dupla", "double")
        self.cmb_arrow_style.currentIndexChanged.connect(self._on_arrow_style_changed)
        s_lay.addWidget(self.cmb_arrow_style)

        # Linha: Sólida / Tracejada
        self.lbl_line_style = QLabel("Traço:")
        s_lay.addWidget(self.lbl_line_style)
        self.cmb_line_style = QComboBox()
        self.cmb_line_style.addItem("Sólido", "solid")
        self.cmb_line_style.addItem("Tracejado", "dashed")
        self.cmb_line_style.currentIndexChanged.connect(self._on_line_style_changed)
        s_lay.addWidget(self.cmb_line_style)

        # Passo: Formato
        self.lbl_step_fmt = QLabel("Formato:")
        s_lay.addWidget(self.lbl_step_fmt)
        self.cmb_step_fmt = QComboBox()
        self.cmb_step_fmt.addItem("1, 2, 3...", "1,2,3")
        self.cmb_step_fmt.addItem("A, B, C...", "A,B,C")
        self.cmb_step_fmt.addItem("I, II, III...", "I,II,III")
        self.cmb_step_fmt.currentIndexChanged.connect(self._on_step_fmt_changed)
        s_lay.addWidget(self.cmb_step_fmt)

        # Texto: Tamanho
        self.lbl_font_size = QLabel("Tamanho do Texto:")
        s_lay.addWidget(self.lbl_font_size)
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 96)
        self.spin_font_size.setValue(24)
        self.spin_font_size.valueChanged.connect(self._on_font_size_changed)
        s_lay.addWidget(self.spin_font_size)

        # Formas: Preenchimento translúcido
        self.chk_filled = QCheckBox("Preenchimento")
        self.chk_filled.toggled.connect(self._on_filled_toggled)
        s_lay.addWidget(self.chk_filled)

        s_lay.addStretch(1)

        self.btn_del_sel = QPushButton("Excluir Selecionado")
        self.btn_del_sel.clicked.connect(self._delete_selected)
        s_lay.addWidget(self.btn_del_sel)

        self.btn_undo = QPushButton("Desfazer")
        self.btn_undo.clicked.connect(self._undo)
        s_lay.addWidget(self.btn_undo)

        self.btn_clear = QPushButton("Limpar Tudo")
        self.btn_clear.clicked.connect(self._clear)
        s_lay.addWidget(self.btn_clear)

        root.addWidget(style_card)

        # Scroll Area com Canvas
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

        self._update_tool_options_visibility("arrow")

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
            self.lbl_zoom.setText("100%")
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
            self._update_tool_options_visibility(tid)

    def _update_tool_options_visibility(self, tid: str) -> None:
        is_arrow = (tid == "arrow")
        is_shape = (tid in ("rect", "ellipse"))
        is_step = (tid == "step")
        is_text = (tid == "text")

        self.lbl_arrow_head.setVisible(is_arrow)
        self.cmb_arrow_style.setVisible(is_arrow)
        self.lbl_line_style.setVisible(is_arrow or is_shape)
        self.cmb_line_style.setVisible(is_arrow or is_shape)
        self.chk_filled.setVisible(is_shape)
        self.lbl_step_fmt.setVisible(is_step)
        self.cmb_step_fmt.setVisible(is_step)
        self.lbl_font_size.setVisible(is_text)
        self.spin_font_size.setVisible(is_text)

    def _on_color_changed(self) -> None:
        hex_code = self.cmb_color.currentData()
        if hex_code:
            self.canvas.current_color = hex_code
            if self.canvas.selected_item:
                self.canvas.selected_item.color = hex_code
                self.canvas._render_cache()

    def _on_width_changed(self, val: int) -> None:
        self.canvas.current_width = val
        if self.canvas.selected_item:
            self.canvas.selected_item.width = val
            self.canvas._render_cache()

    def _on_arrow_style_changed(self) -> None:
        st = self.cmb_arrow_style.currentData()
        if st:
            self.canvas.arrow_style = st
            if self.canvas.selected_item and self.canvas.selected_item.tool_type == "arrow":
                self.canvas.selected_item.arrow_style = st
                self.canvas._render_cache()

    def _on_line_style_changed(self) -> None:
        st = self.cmb_line_style.currentData()
        if st:
            self.canvas.line_style = st
            if self.canvas.selected_item:
                self.canvas.selected_item.style = st
                self.canvas._render_cache()

    def _on_step_fmt_changed(self) -> None:
        fmt = self.cmb_step_fmt.currentData()
        if fmt:
            self.canvas.step_format = fmt
            if self.canvas.selected_item and self.canvas.selected_item.tool_type == "step":
                self.canvas.selected_item.step_format = fmt
                self.canvas._render_cache()

    def _on_font_size_changed(self, val: int) -> None:
        self.canvas.font_size = val
        if self.canvas.selected_item and self.canvas.selected_item.tool_type == "text":
            self.canvas.selected_item.font_size = val
            self.canvas._render_cache()

    def _on_filled_toggled(self, checked: bool) -> None:
        self.canvas.is_filled = checked
        if self.canvas.selected_item and self.canvas.selected_item.tool_type in ("rect", "ellipse"):
            self.canvas.selected_item.filled = checked
            self.canvas._render_cache()

    def _adjust_zoom(self, factor: float) -> None:
        current = self.canvas.get_zoom()
        self._set_zoom(current * factor)

    def _set_zoom(self, zoom: float) -> None:
        self.canvas.set_zoom(zoom)
        self.lbl_zoom.setText(f"{int(self.canvas.get_zoom() * 100)}%")

    def _fit_zoom(self) -> None:
        if not self.canvas.pil_base_image:
            return
        scroll_w = self.scroll.viewport().width() - 20
        scroll_h = self.scroll.viewport().height() - 20
        if scroll_w > 10 and scroll_h > 10:
            scale_w = scroll_w / self.canvas.pil_base_image.width
            scale_h = scroll_h / self.canvas.pil_base_image.height
            fit_zoom = min(scale_w, scale_h, 1.0)
            self._set_zoom(fit_zoom)

    def _undo(self) -> None:
        self.canvas.undo_last()

    def _clear(self) -> None:
        self.canvas.clear_all()

    def _delete_selected(self) -> None:
        self.canvas.delete_selected()

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
