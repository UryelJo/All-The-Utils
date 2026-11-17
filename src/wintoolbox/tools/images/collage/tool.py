"""
Ferramenta: Colagens, Montagens e Gerador de Templates de Fotos.
Permite criar grades interativas livres com formato configurável
ou gerar templates reutilizáveis com detecção automática de slots via Chroma-Key (#00FF00).
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.collage.logic import (
    create_image_collage, detect_chroma_slots, render_template_collage
)
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl
from wintoolbox.ui.widgets.zoomable_image import ZoomableImageCanvas


@register
class ImageCollageTool(Tool):
    id = "images.collage"
    name = "Colagens e Montagens"
    category = "Imagens"
    description = "Crie montagens de fotos em grade ou gerencie templates personalizados com encaixe automático"
    keywords = ["colagem", "montagem", "fotos", "grade", "painel", "mural", "template", "chroma", "pwa"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ImageCollageView(self, parent)


class ImageCollageView(QWidget):
    def __init__(self, tool: ImageCollageTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._grid_images: List[Path] = []
        self._template_base: Optional[Path] = None
        self._template_slots: List[Dict[str, Any]] = []
        self._slot_photos: Dict[int, Path] = {}

        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._build_grid_tab(), "Colagem em Grade")
        tabs.addTab(self._build_template_tab(), "Gerador e Aplicador de Templates")
        root_layout.addWidget(tabs)

    # -------------------------------------------------------------------------
    # Aba 1: Grade Livre
    # -------------------------------------------------------------------------
    def _build_grid_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(8, 10, 8, 8)
        main_layout.setSpacing(14)

        # Coluna Esquerda: Controles e Lista
        left_col = QWidget()
        v_left = QVBoxLayout(left_col)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(10)

        grp_list = QGroupBox("Fotos Selecionadas para a Montagem")
        v_gl = QVBoxLayout(grp_list)
        self.list_grid = QListWidget()
        self.list_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_grid.setIconSize(QSize(50, 50))
        self.list_grid.setGridSize(QSize(68, 68))
        self.list_grid.setFixedHeight(120)
        v_gl.addWidget(self.list_grid)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("Adicionar Fotos...")
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add_grid_photos)
        row_btns.addWidget(btn_add)

        btn_rem = QPushButton("Remover")
        btn_rem.clicked.connect(self._on_remove_grid_photo)
        row_btns.addWidget(btn_rem)

        btn_clr = QPushButton("Limpar")
        btn_clr.clicked.connect(self._on_clear_grid_photos)
        row_btns.addWidget(btn_clr)
        row_btns.addStretch()
        v_gl.addLayout(row_btns)
        v_left.addWidget(grp_list)

        # Configurações da Grade
        grp_cfg = QGroupBox("Layout da Colagem")
        grid_cfg = QGridLayout(grp_cfg)
        grid_cfg.setHorizontalSpacing(12)
        grid_cfg.setVerticalSpacing(8)

        grid_cfg.addWidget(QLabel("Colunas:"), 0, 0)
        self.spin_cols = SliderSpinControl("", 1, 8, 2, suffix=" col")
        self.spin_cols.valueChanged.connect(self._update_grid_preview)
        grid_cfg.addWidget(self.spin_cols, 0, 1)

        grid_cfg.addWidget(QLabel("Espaçamento:"), 0, 2)
        self.spin_spacing = SliderSpinControl("", 0, 60, 12, suffix=" px")
        self.spin_spacing.valueChanged.connect(self._update_grid_preview)
        grid_cfg.addWidget(self.spin_spacing, 0, 3)

        grid_cfg.addWidget(QLabel("Encaixe das fotos:"), 1, 0)
        self.cmb_fit = QComboBox()
        self.cmb_fit.addItem("Preencher e Cortar (Quadrado)", "crop")
        self.cmb_fit.addItem("Ajustar Completo (Com Barras)", "fit")
        self.cmb_fit.currentTextChanged.connect(self._update_grid_preview)
        grid_cfg.addWidget(self.cmb_fit, 1, 1)

        grid_cfg.addWidget(QLabel("Formato de saída:"), 1, 2)
        self.cmb_grid_fmt = QComboBox()
        self.cmb_grid_fmt.addItems(["PNG (Alta Qualidade)", "JPEG (Compacto)", "WEBP (Moderno)"])
        grid_cfg.addWidget(self.cmb_grid_fmt, 1, 3)

        v_left.addWidget(grp_cfg)

        # Botão de Exportação
        btn_export_grid = QPushButton("Exportar Colagem Final...")
        btn_export_grid.setProperty("class", "primary")
        btn_export_grid.setFixedHeight(34)
        btn_export_grid.clicked.connect(self._export_grid_collage)
        v_left.addWidget(btn_export_grid)

        v_left.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna Direita: Preview Interativo com Zoom
        self.canvas_grid = ZoomableImageCanvas(tab)
        main_layout.addWidget(self.canvas_grid, stretch=1)

        return tab

    # -------------------------------------------------------------------------
    # Aba 2: Gerador e Aplicador de Templates
    # -------------------------------------------------------------------------
    def _build_template_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        main_layout.setContentsMargins(8, 10, 8, 8)
        main_layout.setSpacing(14)

        # Coluna Esquerda: Template e Detecção Chroma
        left_col = QWidget()
        v_left = QVBoxLayout(left_col)
        v_left.setContentsMargins(0, 0, 0, 0)
        v_left.setSpacing(10)

        grp_base = QGroupBox("1. Arte Base do Template")
        v_base = QVBoxLayout(grp_base)
        row_base = QHBoxLayout()
        self.txt_template_base = QLineEdit()
        self.txt_template_base.setPlaceholderText("Selecione a arte base (imagem ou layout)...")
        row_base.addWidget(self.txt_template_base, stretch=1)
        btn_load_base = QPushButton("Carregar Arte...")
        btn_load_base.setProperty("class", "primary")
        btn_load_base.clicked.connect(self._on_load_template_base)
        row_base.addWidget(btn_load_base)
        v_base.addLayout(row_base)

        row_chroma = QHBoxLayout()
        btn_detect_chroma = QPushButton("Detectar Slots Verdes (#00FF00)")
        btn_detect_chroma.setToolTip("Localiza automaticamente áreas pintadas em verde na imagem para servir como slots")
        btn_detect_chroma.clicked.connect(self._on_detect_chroma)
        row_chroma.addWidget(btn_detect_chroma)

        self.lbl_slots_count = QLabel("0 slots configurados")
        self.lbl_slots_count.setStyleSheet("font-weight: 500; color: #57A5FF;")
        row_chroma.addWidget(self.lbl_slots_count)
        row_chroma.addStretch()
        v_base.addLayout(row_chroma)
        v_left.addWidget(grp_base)

        grp_fill = QGroupBox("2. Preenchimento Rápido dos Slots")
        v_fill = QVBoxLayout(grp_fill)
        self.list_slots = QListWidget()
        self.list_slots.setFixedHeight(140)
        self.list_slots.itemDoubleClicked.connect(self._on_slot_double_clicked)
        v_fill.addWidget(self.list_slots)

        row_fill_btns = QHBoxLayout()
        btn_fill_batch = QPushButton("Preencher Slots em Lote...")
        btn_fill_batch.clicked.connect(self._on_batch_fill_slots)
        row_fill_btns.addWidget(btn_fill_batch)

        btn_save_tpl = QPushButton("Salvar Template (.wtpl.json)")
        btn_save_tpl.clicked.connect(self._on_save_template_file)
        row_fill_btns.addWidget(btn_save_tpl)

        btn_load_tpl = QPushButton("Abrir Template...")
        btn_load_tpl.clicked.connect(self._on_load_template_file)
        row_fill_btns.addWidget(btn_load_tpl)
        v_fill.addLayout(row_fill_btns)
        v_left.addWidget(grp_fill)

        btn_export_tpl = QPushButton("Exportar Imagem com Fotos Aplicadas...")
        btn_export_tpl.setProperty("class", "primary")
        btn_export_tpl.setFixedHeight(34)
        btn_export_tpl.clicked.connect(self._on_export_template_result)
        v_left.addWidget(btn_export_tpl)

        v_left.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna Direita: Preview do Template
        self.canvas_template = ZoomableImageCanvas(tab)
        main_layout.addWidget(self.canvas_template, stretch=1)

        return tab

    # Handlers Aba 1 (Grade)
    def _on_add_grid_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Fotos",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.heic *.avif);;Todos (*.*)"
        )
        if files:
            for f in files:
                p = Path(f)
                if p not in self._grid_images:
                    self._grid_images.append(p)
            self._sync_grid_list()
            self._update_grid_preview()

    def _on_remove_grid_photo(self):
        curr = self.list_grid.currentRow()
        if 0 <= curr < len(self._grid_images):
            self._grid_images.pop(curr)
            self._sync_grid_list()
            self._update_grid_preview()

    def _on_clear_grid_photos(self):
        self._grid_images.clear()
        self._sync_grid_list()
        self._update_grid_preview()

    def _sync_grid_list(self):
        self.list_grid.clear()
        for idx, p in enumerate(self._grid_images):
            pix = QPixmap(str(p))
            icon = QIcon(pix.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio)) if not pix.isNull() else QApplication.style().standardIcon(QFrame.Style.SP_FileIcon)
            self.list_grid.addItem(QListWidgetItem(icon, f"#{idx + 1}"))

    def _update_grid_preview(self, *_):
        if not self._grid_images:
            self.canvas_grid.set_pixmap(None)
            return

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            fit_mode = self.cmb_fit.currentData() or "crop"
            cols = int(self.spin_cols.value())
            spacing = int(self.spin_spacing.value())
            create_image_collage(
                image_paths=self._grid_images[:16],  # Limite para preview super rápido
                output_path=tmp_path,
                cols=cols,
                spacing=spacing,
                cell_size=(240, 240),
                fit_mode=fit_mode,
                output_format="PNG"
            )
            pix = QPixmap(str(tmp_path))
            self.canvas_grid.set_pixmap(pix, auto_fit=True)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def _export_grid_collage(self):
        if not self._grid_images:
            QMessageBox.warning(self, "Aviso", "Adicione fotos para montar a colagem.")
            return

        fmt_raw = self.cmb_grid_fmt.currentText().split()[0].lower()
        ext = f".{fmt_raw}"
        dest_str, _ = QFileDialog.getSaveFileName(self, "Salvar Colagem", f"colagem{ext}", f"Imagem (*{ext})")
        if not dest_str:
            return

        cols = int(self.spin_cols.value())
        spacing = int(self.spin_spacing.value())
        fit_mode = self.cmb_fit.currentData() or "crop"

        try:
            create_image_collage(
                image_paths=self._grid_images,
                output_path=Path(dest_str),
                cols=cols,
                spacing=spacing,
                cell_size=(600, 600),
                fit_mode=fit_mode,
                output_format=fmt_raw
            )
            QMessageBox.information(self, "Sucesso", f"Colagem salva com sucesso em:\n{dest_str}")
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Falha ao gerar colagem: {ex}")

    # Handlers Aba 2 (Template)
    def _on_load_template_base(self):
        f, _ = QFileDialog.getOpenFileName(self, "Carregar Arte Base do Template", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if f:
            self._template_base = Path(f)
            self.txt_template_base.setText(f)
            pix = QPixmap(f)
            self.canvas_template.set_pixmap(pix, auto_fit=True)

    def _on_detect_chroma(self):
        if not self._template_base or not self._template_base.is_file():
            QMessageBox.warning(self, "Aviso", "Carregue a arte base do template primeiro.")
            return

        try:
            boxes = detect_chroma_slots(self._template_base, chroma_hex="#00FF00")
            self._template_slots = []
            for idx, b in enumerate(boxes):
                self._template_slots.append({"id": idx + 1, "rect": list(b), "corner_radius": 8})

            self._refresh_slots_list()
            self._render_template_preview()
            QMessageBox.information(self, "Detecção Concluída", f"{len(boxes)} slots de fotos foram detectados automaticamente!")
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Falha ao detectar slots: {ex}")

    def _refresh_slots_list(self):
        self.list_slots.clear()
        self.lbl_slots_count.setText(f"{len(self._template_slots)} slots configurados")
        for s in self._template_slots:
            sid = s["id"]
            rect = s["rect"]
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            photo = self._slot_photos.get(sid)
            photo_name = photo.name if photo else "[Vazio - clique duas vezes para escolher]"
            self.list_slots.addItem(f"Slot {sid} ({w}×{h} px): {photo_name}")

    def _on_slot_double_clicked(self, item: QListWidgetItem):
        curr = self.list_slots.currentRow()
        if 0 <= curr < len(self._template_slots):
            sid = self._template_slots[curr]["id"]
            f, _ = QFileDialog.getOpenFileName(self, f"Escolher Foto para Slot #{sid}", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
            if f:
                self._slot_photos[sid] = Path(f)
                self._refresh_slots_list()
                self._render_template_preview()

    def _on_batch_fill_slots(self):
        if not self._template_slots:
            QMessageBox.warning(self, "Aviso", "Nenhum slot disponível. Carregue uma arte ou detecte os slots primeiro.")
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Fotos em Lote", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if files:
            for idx, s in enumerate(self._template_slots):
                if idx < len(files):
                    self._slot_photos[s["id"]] = Path(files[idx])
            self._refresh_slots_list()
            self._render_template_preview()

    def _render_template_preview(self):
        if not self._template_base or not self._template_base.is_file():
            return

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            render_template_collage(
                base_image_path=self._template_base,
                slots=self._template_slots,
                slot_photos=self._slot_photos,
                output_path=tmp_path,
                output_format="PNG"
            )
            pix = QPixmap(str(tmp_path))
            self.canvas_template.set_pixmap(pix, auto_fit=False)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def _on_save_template_file(self):
        if not self._template_base or not self._template_slots:
            QMessageBox.warning(self, "Aviso", "Configure uma arte base e pelo menos um slot antes de salvar.")
            return

        dest_str, _ = QFileDialog.getSaveFileName(self, "Salvar Template", "meu_template.wtpl.json", "Templates (*.wtpl.json)")
        if dest_str:
            data = {
                "base_image": str(self._template_base.resolve()),
                "slots": self._template_slots,
            }
            with open(dest_str, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Template Salvo", f"Template gravado com sucesso em:\n{dest_str}")

    def _on_load_template_file(self):
        src_str, _ = QFileDialog.getOpenFileName(self, "Abrir Template", "", "Templates (*.wtpl.json)")
        if src_str:
            with open(src_str, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._template_base = Path(data.get("base_image", ""))
            self.txt_template_base.setText(str(self._template_base))
            self._template_slots = data.get("slots", [])
            self._slot_photos.clear()
            self._refresh_slots_list()
            if self._template_base.is_file():
                self.canvas_template.set_pixmap(QPixmap(str(self._template_base)), auto_fit=True)

    def _on_export_template_result(self):
        if not self._template_base:
            QMessageBox.warning(self, "Aviso", "Nenhum template ativo.")
            return

        dest_str, _ = QFileDialog.getSaveFileName(self, "Salvar Imagem Final", "montagem.png", "Imagens PNG (*.png);;JPEG (*.jpg);;WEBP (*.webp)")
        if dest_str:
            try:
                render_template_collage(
                    base_image_path=self._template_base,
                    slots=self._template_slots,
                    slot_photos=self._slot_photos,
                    output_path=Path(dest_str)
                )
                QMessageBox.information(self, "Sucesso", f"Montagem gerada e salva com sucesso em:\n{dest_str}")
            except Exception as ex:
                QMessageBox.critical(self, "Erro", f"Falha ao gerar montagem: {ex}")
