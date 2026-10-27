"""
Interface gráfica do Editor Visual de Recorte e Rotação Fina.
"""
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGraphicsItem,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.crop_editor.logic import (
    ASPECT_RATIOS, apply_crop_and_rotation, calculate_aspect_box, process_image_file
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("images.crop_editor.ui")


class CropOverlayItem(QGraphicsRectItem):
    """Retângulo interativo de recorte com alças e grade de terços."""

    def __init__(self, rect: QRectF, parent: Optional[QGraphicsItem] = None):
        super().__init__(rect, parent)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.show_rule_of_thirds = True

    def paint(self, painter: QPainter, option, widget=None):
        r = self.rect()

        # Borda principal da seleção
        pen = QPen(QColor(96, 165, 250), 2, Qt.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(96, 165, 250, 25)))
        painter.drawRect(r)

        # Grade de terços (Rule of Thirds)
        if self.show_rule_of_thirds and r.width() > 30 and r.height() > 30:
            grid_pen = QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine)
            grid_pen.setCosmetic(True)
            painter.setPen(grid_pen)

            w_step = r.width() / 3.0
            h_step = r.height() / 3.0

            # Linhas verticais
            painter.drawLine(QPointF(r.left() + w_step, r.top()), QPointF(r.left() + w_step, r.bottom()))
            painter.drawLine(QPointF(r.left() + 2 * w_step, r.top()), QPointF(r.left() + 2 * w_step, r.bottom()))

            # Linhas horizontais
            painter.drawLine(QPointF(r.left(), r.top() + h_step), QPointF(r.right(), r.top() + h_step))
            painter.drawLine(QPointF(r.left(), r.top() + 2 * h_step), QPointF(r.right(), r.top() + 2 * h_step))


@register
class CropEditorTool(Tool):
    id = "images.crop_editor"
    name = "Editor de Recorte e Rotação"
    category = "Imagens e Mídia"
    description = "Recorte visual com proporções fixas (1:1, 16:9, 4:5, A4), grade de regra dos terços e rotação angular fina"
    keywords = ["recorte", "crop", "cortar", "foto", "proporção", "enquadramento", "rotação", "terços", "instagram"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CropEditorView(self, parent)


class CropEditorView(QWidget):
    def __init__(self, tool: CropEditorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._current_path: Optional[Path] = None
        self._current_pil_img: Optional[Image.Image] = None

        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Barra de Controles Superiores
        ctrl_card = QFrame()
        ctrl_card.setObjectName("Card")
        c_lay = QHBoxLayout(ctrl_card)
        c_lay.setContentsMargins(14, 10, 14, 10)
        c_lay.setSpacing(12)

        self.btn_open = QPushButton("Abrir Imagem...")
        self.btn_open.setProperty("accent", True)
        self.btn_open.clicked.connect(self._open_file_dialog)
        c_lay.addWidget(self.btn_open)

        c_lay.addWidget(QLabel("Proporção:"))
        self.cmb_ratio = QComboBox()
        for label in ASPECT_RATIOS.keys():
            self.cmb_ratio.addItem(label)
        self.cmb_ratio.currentIndexChanged.connect(self._on_ratio_changed)
        c_lay.addWidget(self.cmb_ratio)

        # Rotação fina
        c_lay.addWidget(QLabel("Rotação Fina:"))
        self.slider_rot = QSlider(Qt.Horizontal)
        self.slider_rot.setRange(-45, 45)
        self.slider_rot.setValue(0)
        self.slider_rot.setFixedWidth(140)
        self.slider_rot.valueChanged.connect(self._on_rotation_slider_changed)
        c_lay.addWidget(self.slider_rot)

        self.spin_rot = QSpinBox()
        self.spin_rot.setRange(-45, 45)
        self.spin_rot.setValue(0)
        self.spin_rot.setSuffix("°")
        self.spin_rot.valueChanged.connect(self._on_rotation_spin_changed)
        c_lay.addWidget(self.spin_rot)

        self.btn_reset_rot = QPushButton("Resetar Ângulo")
        self.btn_reset_rot.clicked.connect(lambda: self.slider_rot.setValue(0))
        c_lay.addWidget(self.btn_reset_rot)

        c_lay.addStretch(1)

        # Resolução resultante
        self.lbl_dims = QLabel("Nenhuma imagem carregada")
        self.lbl_dims.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 11px;")
        c_lay.addWidget(self.lbl_dims)

        root.addWidget(ctrl_card)

        # Área de Visualização Gráfica (Canvas com QGraphicsView)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setStyleSheet("background-color: #1a1a1a; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;")
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        self.crop_item = CropOverlayItem(QRectF(0, 0, 100, 100))
        self.crop_item.setVisible(False)
        self.scene.addItem(self.crop_item)

        root.addWidget(self.view, stretch=1)

        # Barra de Ações Inferiores
        act_card = QFrame()
        act_card.setObjectName("Card")
        a_lay = QHBoxLayout(act_card)
        a_lay.setContentsMargins(14, 10, 14, 10)
        a_lay.setSpacing(10)

        self.btn_copy = QPushButton("Copiar Imagem Recortada")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        a_lay.addWidget(self.btn_copy)

        a_lay.addStretch(1)

        self.btn_save = QPushButton("Salvar Recorte Como...")
        self.btn_save.setEnabled(False)
        self.btn_save.setProperty("accent", True)
        self.btn_save.clicked.connect(self._save_cropped)
        a_lay.addWidget(self.btn_save)

        root.addWidget(act_card)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para Recorte",
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
                self._current_pil_img = ImageOps.exif_transpose(img.copy())

            self._update_scene_view()
            self.btn_copy.setEnabled(True)
            self.btn_save.setEnabled(True)
            show_toast(self, f"Imagem carregada: {path.name}", duration_ms=2500)
        except Exception as e:
            _log.error(f"Erro ao carregar imagem: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo de imagem:\n{e}")

    def _update_scene_view(self) -> None:
        if not self._current_pil_img:
            return

        angle = self.slider_rot.value()
        img = self._current_pil_img
        if abs(angle) > 0.01:
            img = img.rotate(angle, resample=Image.BICUBIC, expand=False)

        # Converte PIL para QPixmap
        data = img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg)

        self.pixmap_item.setPixmap(pix)
        self.scene.setSceneRect(0, 0, img.width, img.height)

        # Ajusta caixa de recorte pela proporção
        ratio_key = self.cmb_ratio.currentText()
        ratio = ASPECT_RATIOS.get(ratio_key)
        x1, y1, x2, y2 = calculate_aspect_box(img.width, img.height, ratio)

        self.crop_item.setRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        self.crop_item.setVisible(True)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        self._update_dim_label()

    def _on_ratio_changed(self) -> None:
        if not self._current_pil_img:
            return
        ratio_key = self.cmb_ratio.currentText()
        ratio = ASPECT_RATIOS.get(ratio_key)
        img = self._current_pil_img
        x1, y1, x2, y2 = calculate_aspect_box(img.width, img.height, ratio)
        self.crop_item.setRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        self._update_dim_label()

    def _on_rotation_slider_changed(self, val: int) -> None:
        self.spin_rot.blockSignals(True)
        self.spin_rot.setValue(val)
        self.spin_rot.blockSignals(False)
        self._update_scene_view()

    def _on_rotation_spin_changed(self, val: int) -> None:
        self.slider_rot.blockSignals(True)
        self.slider_rot.setValue(val)
        self.slider_rot.blockSignals(False)
        self._update_scene_view()

    def _get_current_crop_box(self) -> Tuple[int, int, int, int]:
        rect = self.crop_item.rect()
        pos = self.crop_item.pos()
        x1 = int(rect.x() + pos.x())
        y1 = int(rect.y() + pos.y())
        x2 = int(x1 + rect.width())
        y2 = int(y1 + rect.height())
        return (x1, y1, x2, y2)

    def _update_dim_label(self) -> None:
        if not self._current_pil_img:
            self.lbl_dims.setText("Nenhuma imagem carregada")
            return
        x1, y1, x2, y2 = self._get_current_crop_box()
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        self.lbl_dims.setText(f"Resolução do Recorte: {w} × {h} px  (Original: {self._current_pil_img.width} × {self._current_pil_img.height} px)")

    def _get_cropped_pil_image(self) -> Optional[Image.Image]:
        if not self._current_pil_img:
            return None
        box = self._get_current_crop_box()
        angle = self.slider_rot.value()
        return apply_crop_and_rotation(self._current_pil_img, box, angle)

    def _copy_to_clipboard(self) -> None:
        cropped = self._get_cropped_pil_image()
        if not cropped:
            return
        data = cropped.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(data, cropped.width, cropped.height, QImage.Format_RGBA8888)
        QApplication.clipboard().setImage(qimg)
        show_toast(self, "Imagem recortada copiada para a área de transferência!", duration_ms=2500)

    def _save_cropped(self) -> None:
        if not self._current_path or not self._current_pil_img:
            return

        suggested = self._current_path.with_stem(self._current_path.stem + "_recorte")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Recorte",
            str(suggested),
            "Imagem PNG (*.png);;Imagem JPEG (*.jpg);;Imagem WebP (*.webp)"
        )
        if not save_path:
            return

        target = Path(save_path)
        box = self._get_current_crop_box()
        angle = self.slider_rot.value()

        def worker(ctx):
            process_image_file(self._current_path, target, box, angle)
            return target

        def on_done(saved_file: Path):
            show_toast(self, f"Arquivo salvo com sucesso em {saved_file.name}!", duration_ms=3000)

        def on_error(err: Exception):
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar a imagem recortada:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
                self.load_image(p)
                break
