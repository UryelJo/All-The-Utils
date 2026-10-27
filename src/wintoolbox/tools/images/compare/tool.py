"""
Interface gráfica do Comparador de Duas Imagens.
"""
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSlider,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.compare.logic import (
    ComparisonMetrics, calculate_metrics, create_slider_composition, generate_diff_heatmap
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("images.compare.ui")


@register
class CompareTool(Tool):
    id = "images.compare"
    name = "Comparador de Imagens"
    category = "Imagens"
    description = "Compare duas imagens com slider antes/depois, mapa de diferença de pixels e modo piscante para avaliar compressões"
    keywords = ["comparar", "diferença", "slider", "antes", "depois", "compressão", "fidelidade", "psnr", "pixels"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CompareView(self, parent)


class CompareView(QWidget):
    def __init__(self, tool: CompareTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()

        self._img_a: Optional[Image.Image] = None
        self._img_b: Optional[Image.Image] = None
        self._name_a: str = "Imagem A"
        self._name_b: str = "Imagem B"

        self._current_mode: str = "slider"  # "slider", "diff", "flicker"
        self._flicker_state: bool = False
        self._flicker_timer = QTimer(self)
        self._flicker_timer.setInterval(400)
        self._flicker_timer.timeout.connect(self._on_flicker_tick)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        root.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Painel Superior: Carregamento dos dois arquivos
        files_card = QFrame()
        files_card.setObjectName("Card")
        f_lay = QHBoxLayout(files_card)
        f_lay.setContentsMargins(14, 10, 14, 10)
        f_lay.setSpacing(12)

        self.btn_load_a = QPushButton("Carregar Imagem A (Original)...")
        self.btn_load_a.setProperty("accent", True)
        self.btn_load_a.clicked.connect(lambda: self._load_file("A"))
        f_lay.addWidget(self.btn_load_a)

        self.lbl_file_a = QLabel("Nenhuma imagem selecionada")
        self.lbl_file_a.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        f_lay.addWidget(self.lbl_file_a, stretch=1)

        self.btn_swap = QPushButton("Inverter (A ↔ B)")
        self.btn_swap.clicked.connect(self._swap_images)
        f_lay.addWidget(self.btn_swap)

        self.btn_load_b = QPushButton("Carregar Imagem B (Modificada)...")
        self.btn_load_b.setProperty("accent", True)
        self.btn_load_b.clicked.connect(lambda: self._load_file("B"))
        f_lay.addWidget(self.btn_load_b)

        self.lbl_file_b = QLabel("Nenhuma imagem selecionada")
        self.lbl_file_b.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        f_lay.addWidget(self.lbl_file_b, stretch=1)

        root.addWidget(files_card)

        # Painel de Modo de Comparação e Controles
        ctrl_card = QFrame()
        ctrl_card.setObjectName("Card")
        c_lay = QHBoxLayout(ctrl_card)
        c_lay.setContentsMargins(14, 10, 14, 10)
        c_lay.setSpacing(12)

        c_lay.addWidget(QLabel("Modo de Comparação:"))
        self.mode_group = QButtonGroup(self)

        rb_slider = QRadioButton("Slider Cortina (Antes / Depois)")
        rb_slider.setChecked(True)
        self.mode_group.addButton(rb_slider, 0)
        c_lay.addWidget(rb_slider)

        rb_diff = QRadioButton("Diferença de Pixels (Mapa)")
        self.mode_group.addButton(rb_diff, 1)
        c_lay.addWidget(rb_diff)

        rb_flicker = QRadioButton("Modo Piscante (Flicker)")
        self.mode_group.addButton(rb_flicker, 2)
        c_lay.addWidget(rb_flicker)

        self.mode_group.buttonClicked.connect(self._on_mode_changed)

        # Slider Cortina
        self.slider_split = QSlider(Qt.Horizontal)
        self.slider_split.setRange(0, 100)
        self.slider_split.setValue(50)
        self.slider_split.setFixedWidth(160)
        self.slider_split.valueChanged.connect(self._update_display)
        c_lay.addWidget(self.slider_split)

        self.lbl_split = QLabel("50%")
        c_lay.addWidget(self.lbl_split)

        c_lay.addStretch(1)

        # Botão Iniciar/Parar Piscada
        self.btn_flicker_toggle = QPushButton("Alternar A/B")
        self.btn_flicker_toggle.setVisible(False)
        self.btn_flicker_toggle.clicked.connect(self._toggle_flicker_manual)
        c_lay.addWidget(self.btn_flicker_toggle)

        root.addWidget(ctrl_card)

        # Cartão de Métricas
        self.metrics_card = QFrame()
        self.metrics_card.setObjectName("Card")
        m_lay = QHBoxLayout(self.metrics_card)
        m_lay.setContentsMargins(14, 8, 14, 8)
        self.lbl_metrics = QLabel("Carregue ambas as imagens para calcular métricas de fidelidade visual (PSNR, MSE e percentual de diferença).")
        self.lbl_metrics.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        m_lay.addWidget(self.lbl_metrics)
        root.addWidget(self.metrics_card)

        # Visualizador Central
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setStyleSheet("background-color: #121212; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;")

        self.lbl_preview = QLabel("Carregue a Imagem A e a Imagem B para visualizar a comparação")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        self.scroll.setWidget(self.lbl_preview)
        root.addWidget(self.scroll, stretch=1)

        # Barra Inferior
        bot_card = QFrame()
        bot_card.setObjectName("Card")
        b_lay = QHBoxLayout(bot_card)
        b_lay.setContentsMargins(14, 10, 14, 10)
        b_lay.setSpacing(10)

        self.btn_copy = QPushButton("Copiar Visualização Comparativa")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_view)
        b_lay.addWidget(self.btn_copy)

        b_lay.addStretch(1)

        self.btn_save = QPushButton("Salvar Imagem Comparativa...")
        self.btn_save.setEnabled(False)
        self.btn_save.setProperty("accent", True)
        self.btn_save.clicked.connect(self._save_view)
        b_lay.addWidget(self.btn_save)

        root.addWidget(bot_card)

    def _load_file(self, target: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar Imagem {target}",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;Todos os Arquivos (*.*)"
        )
        if not path:
            return

        p = Path(path)
        try:
            with Image.open(p) as img:
                from PIL import ImageOps
                loaded = ImageOps.exif_transpose(img.copy())

            if target == "A":
                self._img_a = loaded
                self._name_a = p.name
                self.lbl_file_a.setText(f"{p.name} ({loaded.width}x{loaded.height})")
            else:
                self._img_b = loaded
                self._name_b = p.name
                self.lbl_file_b.setText(f"{p.name} ({loaded.width}x{loaded.height})")

            self._on_images_updated()
            show_toast(self, f"Imagem {target} carregada: {p.name}", duration_ms=2000)
        except Exception as e:
            _log.error(f"Erro ao carregar imagem {target}: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir o arquivo:\n{e}")

    def _swap_images(self) -> None:
        self._img_a, self._img_b = self._img_b, self._img_a
        self._name_a, self._name_b = self._name_b, self._name_a

        txt_a = self.lbl_file_a.text()
        self.lbl_file_a.setText(self.lbl_file_b.text())
        self.lbl_file_b.setText(txt_a)

        self._on_images_updated()

    def _on_images_updated(self) -> None:
        if self._img_a and self._img_b:
            # Calcula métricas
            m = calculate_metrics(self._img_a, self._img_b)
            psnr_str = f"{m.psnr_db} dB" if m.psnr_db != 999.0 else "Infinita (Idênticas)"
            status = "Idênticas (100% de coincidência)" if m.identical else f"{m.difference_percentage}% de pixels com variação"
            self.lbl_metrics.setText(
                f"<b>Resolução Base:</b> {m.width} × {m.height} px  •  "
                f"<b>PSNR:</b> {psnr_str}  •  <b>MSE:</b> {m.mean_squared_error}  •  "
                f"<b>Status:</b> {status}"
            )
            self.btn_copy.setEnabled(True)
            self.btn_save.setEnabled(True)
        elif self._img_a:
            self.lbl_metrics.setText(f"Imagem A carregada ({self._img_a.width}x{self._img_a.height} px). Carregue a Imagem B para comparar.")
        elif self._img_b:
            self.lbl_metrics.setText(f"Imagem B carregada ({self._img_b.width}x{self._img_b.height} px). Carregue a Imagem A para comparar.")

        self._update_display()

    def _on_mode_changed(self, button) -> None:
        idx = self.mode_group.id(button)
        if idx == 0:
            self._current_mode = "slider"
            self.slider_split.setVisible(True)
            self.lbl_split.setVisible(True)
            self.btn_flicker_toggle.setVisible(False)
            self._flicker_timer.stop()
        elif idx == 1:
            self._current_mode = "diff"
            self.slider_split.setVisible(False)
            self.lbl_split.setVisible(False)
            self.btn_flicker_toggle.setVisible(False)
            self._flicker_timer.stop()
        elif idx == 2:
            self._current_mode = "flicker"
            self.slider_split.setVisible(False)
            self.lbl_split.setVisible(False)
            self.btn_flicker_toggle.setVisible(True)
            self._flicker_timer.start()

        self._update_display()

    def _toggle_flicker_manual(self) -> None:
        self._flicker_state = not self._flicker_state
        self._update_display()

    def _on_flicker_tick(self) -> None:
        self._flicker_state = not self._flicker_state
        self._update_display()

    def _generate_current_pil_view(self) -> Optional[Image.Image]:
        if not self._img_a and not self._img_b:
            return None
        if not self._img_b:
            return self._img_a
        if not self._img_a:
            return self._img_b

        if self._current_mode == "slider":
            ratio = self.slider_split.value() / 100.0
            return create_slider_composition(self._img_a, self._img_b, split_ratio=ratio)
        elif self._current_mode == "diff":
            return generate_diff_heatmap(self._img_a, self._img_b, amplification=4.0)
        elif self._current_mode == "flicker":
            return self._img_b if self._flicker_state else self._img_a
        return self._img_a

    def _update_display(self) -> None:
        self.lbl_split.setText(f"{self.slider_split.value()}%")
        pil_img = self._generate_current_pil_view()
        if not pil_img:
            return

        data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg)

        self.lbl_preview.setPixmap(pix)
        self.lbl_preview.adjustSize()

    def _copy_view(self) -> None:
        pil_img = self._generate_current_pil_view()
        if not pil_img:
            return
        data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        QApplication.clipboard().setImage(qimg)
        show_toast(self, "Imagem comparativa copiada para a área de transferência!", duration_ms=2500)

    def _save_view(self) -> None:
        pil_img = self._generate_current_pil_view()
        if not pil_img:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Visualização Comparativa",
            "comparacao_imagem.png",
            "Imagem PNG (*.png);;Imagem JPEG (*.jpg)"
        )
        if not save_path:
            return

        target = Path(save_path)
        if target.suffix.lower() in (".jpg", ".jpeg"):
            pil_img.convert("RGB").save(target, format="JPEG", quality=95)
        else:
            pil_img.save(target)

        show_toast(self, f"Salvo com sucesso em {target.name}!", duration_ms=3000)
