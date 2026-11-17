"""
Ferramenta: Visualizador e Removedor de Metadados EXIF.
Permite inspecionar dados de câmera e GPS de forma limpa e organizada,
traduzindo códigos técnicos e limpando metadados em lote para privacidade.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTabWidget, QTableWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.exif.logic import get_exif_info, strip_metadata
from wintoolbox.ui.widgets.batch_input import BatchInputWidget
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

EXIF_IMAGE_EXTS = [".jpg", ".jpeg", ".jfif", ".heic", ".heif", ".hif", ".avif", ".tiff", ".tif", ".png", ".webp"]


@register
class ImageExifTool(Tool):
    id = "images.exif"
    name = "Metadados EXIF e Privacidade"
    category = "Imagens"
    description = "Inspecione dados de câmera e localização GPS em fotos e remova metadados em lote para privacidade"
    keywords = ["exif", "metadados", "gps", "privacidade", "camera", "remover", "anonimizar", "data", "fotos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ImageExifView(self, parent)


class ImageExifView(QWidget):
    def __init__(self, tool: ImageExifTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._current_maps_url: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        tabs = QTabWidget()
        tabs.addTab(self._build_inspect_tab(), "Inspecionar Metadados")
        tabs.addTab(self._build_batch_tab(), "Remoção e Limpeza em Lote")
        layout.addWidget(tabs)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _build_inspect_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Barra de seleção de arquivo
        row_sel = QHBoxLayout()
        self.txt_inspect_path = QLineEdit()
        self.txt_inspect_path.setPlaceholderText("Selecione uma imagem para inspecionar...")
        self.txt_inspect_path.setReadOnly(True)
        row_sel.addWidget(self.txt_inspect_path, stretch=1)

        btn_browse = QPushButton("Selecionar Imagem...")
        btn_browse.setProperty("class", "primary")
        btn_browse.clicked.connect(self._select_inspect_image)
        row_sel.addWidget(btn_browse)
        layout.addLayout(row_sel)

        # Card de Resumo com Layout Espaçado e Limpo
        card = QFrame()
        card.setProperty("class", "card")
        card.setStyleSheet("QFrame { background-color: #191B1F; border: 1px solid #2B303A; border-radius: 8px; padding: 14px; }")
        l_card = QGridLayout(card)
        l_card.setHorizontalSpacing(16)
        l_card.setVerticalSpacing(10)

        # Labels com estilos distintos para chave e valor
        def _lbl_key(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet("font-weight: 600; color: #8F96A0; font-size: 12px;")
            return l

        def _lbl_val() -> QLabel:
            l = QLabel("-")
            l.setStyleSheet("font-weight: 500; color: #E0E4E8; font-size: 13px;")
            return l

        self.lbl_make = _lbl_val()
        self.lbl_model = _lbl_val()
        self.lbl_lens = _lbl_val()
        self.lbl_dims = _lbl_val()
        self.lbl_date = _lbl_val()
        self.lbl_exposure = _lbl_val()
        self.lbl_fnumber = _lbl_val()
        self.lbl_iso = _lbl_val()
        self.lbl_orient = _lbl_val()
        self.lbl_gps = _lbl_val()

        # Linha 0: Fabricante & Modelo da Câmera
        l_card.addWidget(_lbl_key("Fabricante:"), 0, 0)
        l_card.addWidget(self.lbl_make, 0, 1)
        l_card.addWidget(_lbl_key("Modelo da Câmera:"), 0, 2)
        l_card.addWidget(self.lbl_model, 0, 3)

        # Linha 1: Lente & Dimensões
        l_card.addWidget(_lbl_key("Modelo da Lente:"), 1, 0)
        l_card.addWidget(self.lbl_lens, 1, 1)
        l_card.addWidget(_lbl_key("Resolução da Foto:"), 1, 2)
        l_card.addWidget(self.lbl_dims, 1, 3)

        # Linha 2: Exposição, Abertura e ISO
        l_card.addWidget(_lbl_key("Tempo de Exposição:"), 2, 0)
        l_card.addWidget(self.lbl_exposure, 2, 1)
        l_card.addWidget(_lbl_key("Abertura (f-stop):"), 2, 2)
        l_card.addWidget(self.lbl_fnumber, 2, 3)

        # Linha 3: Data e Orientação
        l_card.addWidget(_lbl_key("Data de Captura:"), 3, 0)
        l_card.addWidget(self.lbl_date, 3, 1)
        l_card.addWidget(_lbl_key("Orientação EXIF:"), 3, 2)
        l_card.addWidget(self.lbl_orient, 3, 3)

        # Linha 4: Coordenadas GPS
        l_card.addWidget(_lbl_key("Localização GPS:"), 4, 0)
        row_gps = QHBoxLayout()
        row_gps.addWidget(self.lbl_gps)
        self.btn_maps = QPushButton("Ver no Google Maps")
        self.btn_maps.setFixedHeight(26)
        self.btn_maps.setEnabled(False)
        self.btn_maps.clicked.connect(self._open_maps)
        row_gps.addWidget(self.btn_maps)
        row_gps.addStretch()
        l_card.addLayout(row_gps, 4, 1, 1, 3)

        layout.addWidget(card)

        # Tabela completa de Tags Traduzidas
        layout.addWidget(QLabel("Todas as Tags EXIF Detectadas (Decodificadas):"))
        self.table_tags = QTableWidget()
        self.table_tags.setColumnCount(3)
        self.table_tags.setHorizontalHeaderLabels(["ID da Tag", "Nome do Metadado", "Valor Traduzido"])
        self.table_tags.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_tags.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_tags.verticalHeader().setVisible(False)
        self.table_tags.setFixedHeight(240)
        enable_sorting_on_table(self.table_tags)
        layout.addWidget(self.table_tags)

        return w

    def _select_inspect_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem com EXIF",
            "",
            "Imagens (*.jpg *.jpeg *.jfif *.heic *.heif *.hif *.avif *.tiff *.tif *.png *.webp)"
        )
        if not f:
            return

        self.txt_inspect_path.setText(f)
        p = Path(f)
        data = get_exif_info(p)

        self.lbl_make.setText(data["camera_make"])
        self.lbl_model.setText(data["camera_model"])
        self.lbl_lens.setText(data["lens_model"])
        self.lbl_dims.setText(data["dimensions"])
        self.lbl_date.setText(data["date_time"])
        self.lbl_exposure.setText(data["exposure"])
        self.lbl_fnumber.setText(data["f_number"])
        self.lbl_orient.setText(data["orientation"])

        if data["gps_lat"] is not None:
            self.lbl_gps.setText(f"Lat: {data['gps_lat']}, Lon: {data['gps_lon']}")
            self.btn_maps.setEnabled(True)
            self._current_maps_url = data["gps_url"]
        else:
            self.lbl_gps.setText("Nenhum dado de GPS encontrado.")
            self.btn_maps.setEnabled(False)
            self._current_maps_url = None

        # Preenche tabela
        raw = data["raw_tags"]
        with batch_table_update(self.table_tags):
            self.table_tags.setRowCount(len(raw))
            for r, (tid, tname, tval) in enumerate(raw):
                sort_tid = tid if isinstance(tid, (int, float)) else str(tid)
                self.table_tags.setItem(r, 0, SmartTableWidgetItem(str(tid), sort_value=sort_tid))
                self.table_tags.setItem(r, 1, SmartTableWidgetItem(str(tname)))
                self.table_tags.setItem(r, 2, SmartTableWidgetItem(str(tval)))

    def _open_maps(self):
        if self._current_maps_url:
            QDesktopServices.openUrl(QUrl(self._current_maps_url))

    def _build_batch_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Widget evoluído de entrada de lote (Ícones / Miniaturas, Pastas, sem badges)
        self.batch_input = BatchInputWidget(allowed_extensions=EXIF_IMAGE_EXTS, parent=w)
        layout.addWidget(self.batch_input)

        # Barra de Destino e Ação
        card_action = QFrame()
        card_action.setProperty("class", "card")
        l_act = QHBoxLayout(card_action)
        l_act.setSpacing(10)

        self.btn_strip = QPushButton("Limpar e Anonimizar Imagens Selecionadas")
        self.btn_strip.setProperty("class", "primary")
        self.btn_strip.setFixedHeight(36)
        self.btn_strip.clicked.connect(self._run_strip_batch)
        l_act.addWidget(self.btn_strip)

        l_act.addStretch()
        self.lbl_strip_status = QLabel("")
        self.lbl_strip_status.setStyleSheet("font-size: 12px; color: #8F96A0;")
        l_act.addWidget(self.lbl_strip_status)

        layout.addWidget(card_action)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        return w

    def _run_strip_batch(self):
        files = self.batch_input.get_discovered_files()
        if not files:
            QMessageBox.warning(self, "Aviso", "Por favor, adicione imagens na lista acima primeiro.")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Selecionar Diretório de Saída para as Imagens Limpas")
        if not out_dir:
            return

        out_path = Path(out_dir)
        total = len(files)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_strip.setEnabled(False)

        def _task(ctx):
            success_count = 0
            for idx, disc in enumerate(files):
                if ctx.is_cancelled:
                    break
                src = disc.source_path
                dst = out_path / src.name
                if strip_metadata(src, dst):
                    success_count += 1
                ctx.set_progress(idx + 1, total)
            return success_count

        def _on_done(success_count):
            self.btn_strip.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.lbl_strip_status.setText(f"{success_count} de {total} imagens limpas com sucesso!")
            QMessageBox.information(
                self,
                "Concluído",
                f"{success_count} imagens foram limpas e salvas em:\n{out_path}"
            )

        def _on_error(err):
            self.btn_strip.setEnabled(True)
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Erro", f"Falha durante a limpeza: {err}")

        self.runner.run_async(_task, on_success=_on_done, on_error=_on_error)
