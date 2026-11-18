"""
Painel reutilizável de pré-visualização ao vivo para ferramentas de imagem.
Permite alternar entre Original e Resultado, com atualização em segundo plano e debounce.
"""
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget
)

from wintoolbox.ui.widgets.zoomable_image import ZoomableImageCanvas


class ImageLivePreviewPanel(QFrame):
    """
    Painel de preview interativo com debounce.
    Recebe um caminho de imagem e uma função geradora de preview:
    callback(src_path: Path, params: dict) -> PIL.Image ou QPixmap.
    """
    def __init__(
        self,
        title: str = "Prévia",
        parent: Optional[QWidget] = None,
        debounce_ms: int = 180
    ):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #16181A; border-radius: 8px; }")

        self._debounce_ms = debounce_ms
        self._current_src: Optional[Path] = None
        self._current_params: Dict[str, Any] = {}
        self._preview_fn: Optional[Callable[[Path, Dict[str, Any]], Any]] = None

        self._cached_original_pixmap: Optional[QPixmap] = None
        self._cached_result_pixmap: Optional[QPixmap] = None
        self._is_first_load: bool = True

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_render)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header com título e seletor Antes / Depois
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self._lbl_title = QLabel(title, self)
        self._lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #E0E4E8;")
        top_bar.addWidget(self._lbl_title)

        top_bar.addStretch()

        self._status_lbl = QLabel("", self)
        self._status_lbl.setStyleSheet("font-size: 11px; color: #8F96A0;")
        top_bar.addWidget(self._status_lbl)

        self._btn_group = QButtonGroup(self)
        self._btn_original = QPushButton("Original", self)
        self._btn_original.setCheckable(True)
        self._btn_original.setFixedHeight(24)
        self._btn_group.addButton(self._btn_original, 0)
        top_bar.addWidget(self._btn_original)

        self._btn_result = QPushButton("Resultado", self)
        self._btn_result.setCheckable(True)
        self._btn_result.setChecked(True)
        self._btn_result.setFixedHeight(24)
        self._btn_group.addButton(self._btn_result, 1)
        top_bar.addWidget(self._btn_result)

        self._btn_original.clicked.connect(self._on_mode_toggled)
        self._btn_result.clicked.connect(self._on_mode_toggled)

        layout.addLayout(top_bar)

        # Canvas com zoom
        self._canvas = ZoomableImageCanvas(self, show_toolbar=True)
        layout.addWidget(self._canvas, stretch=1)

    def set_preview_generator(self, fn: Callable[[Path, Dict[str, Any]], Any]) -> None:
        """Define a função de processamento de preview."""
        self._preview_fn = fn

    def set_source_file(self, path: Optional[Union[str, Path]]) -> None:
        """Atualiza o arquivo ativo de entrada."""
        p = Path(path) if path else None
        if p != self._current_src:
            self._current_src = p
            self._cached_original_pixmap = None
            self._cached_result_pixmap = None
            self._is_first_load = True
            if p and p.is_file():
                # Carrega original para cache com Pillow para suporte completo (HEIC, AVIF, TIFF, WEBP, etc.)
                try:
                    from PIL import Image, ImageOps
                    import io
                    with Image.open(p) as pil_im:
                        pil_im = ImageOps.exif_transpose(pil_im)
                        if pil_im.mode in ("RGBA", "LA", "P") or (pil_im.mode == "RGB" and "transparency" in pil_im.info):
                            pil_im = pil_im.convert("RGBA")
                        elif pil_im.mode != "RGB":
                            pil_im = pil_im.convert("RGB")
                        buf = io.BytesIO()
                        pil_im.save(buf, format="PNG")
                        pix = QPixmap()
                        pix.loadFromData(buf.getvalue())
                        if not pix.isNull():
                            self._cached_original_pixmap = pix
                except Exception:
                    try:
                        pix = QPixmap(str(p))
                        if not pix.isNull():
                            self._cached_original_pixmap = pix
                    except Exception:
                        self._cached_original_pixmap = None
            self.request_update()

    def update_params(self, params: Dict[str, Any]) -> None:
        """Atualiza os parâmetros de visualização e dispara debounce."""
        self._current_params = dict(params)
        self.request_update()

    def request_update(self) -> None:
        if not self._current_src or not self._current_src.is_file():
            self._canvas.set_pixmap(None)
            self._status_lbl.setText("Selecione um arquivo para ver a prévia")
            return
        self._status_lbl.setText("Atualizando...")
        self._timer.start(self._debounce_ms)

    def _on_mode_toggled(self) -> None:
        if self._btn_original.isChecked():
            self._canvas.set_pixmap(self._cached_original_pixmap, auto_fit=False)
        else:
            self._canvas.set_pixmap(self._cached_result_pixmap, auto_fit=False)

    def _do_render(self) -> None:
        if not self._current_src or not self._preview_fn:
            self._status_lbl.setText("")
            return

        try:
            result = self._preview_fn(self._current_src, self._current_params)
            if result is None:
                self._status_lbl.setText("")
                return

            if isinstance(result, QPixmap):
                self._cached_result_pixmap = result
            else:
                # Assumir PIL Image
                import io
                buf = io.BytesIO()
                result.save(buf, format="PNG")
                pix = QPixmap()
                pix.loadFromData(buf.getvalue())
                self._cached_result_pixmap = pix

            if self._btn_result.isChecked():
                auto_fit = getattr(self, "_is_first_load", True)
                self._canvas.set_pixmap(self._cached_result_pixmap, auto_fit=auto_fit)
                self._is_first_load = False
            self._status_lbl.setText("Pronto")
        except Exception as ex:
            self._status_lbl.setText(f"Erro na prévia: {ex}")

    @property
    def canvas(self) -> ZoomableImageCanvas:
        return self._canvas

