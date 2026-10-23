"""
Ferramenta: Visualizador e Removedor de Metadados EXIF.
Permite inspecionar dados de câmera e GPS e limpar metadados em lote para privacidade.
"""
import os
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.images.exif.logic import (
    get_exif_capture_date, get_exif_info, strip_metadata
)

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
        self.batch_files: List[Path] = []
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

        # Cabeçalho
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
        btn_browse.clicked.connect(self._select_inspect_image)
        row_sel.addWidget(btn_browse)
        layout.addLayout(row_sel)

        # Cards de Resumo
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QGridLayout(card)
        l_card.setHorizontalSpacing(20)
        l_card.setVerticalSpacing(8)

        self.lbl_camera = QLabel("-")
        self.lbl_date = QLabel("-")
        self.lbl_exposure = QLabel("-")
        self.lbl_iso = QLabel("-")
        self.lbl_gps = QLabel("-")

        l_card.addWidget(QLabel("Câmera / Modelo:"), 0, 0)
        l_card.addWidget(self.lbl_camera, 0, 1)
        l_card.addWidget(QLabel("Data de Captura:"), 0, 2)
        l_card.addWidget(self.lbl_date, 0, 3)

        l_card.addWidget(QLabel("Exposição / Abertura:"), 1, 0)
        l_card.addWidget(self.lbl_exposure, 1, 1)
        l_card.addWidget(QLabel("Sensibilidade ISO:"), 1, 2)
        l_card.addWidget(self.lbl_iso, 1, 3)

        l_card.addWidget(QLabel("Coordenadas GPS:"), 2, 0)
        row_gps = QHBoxLayout()
        row_gps.addWidget(self.lbl_gps)
        self.btn_maps = QPushButton("Abrir no Google Maps")
        self.btn_maps.setEnabled(False)
        self.btn_maps.clicked.connect(self._open_maps)
        row_gps.addWidget(self.btn_maps)
        row_gps.addStretch()
        l_card.addLayout(row_gps, 2, 1, 1, 3)

        layout.addWidget(card)

        # Tabela completa de Tags
        layout.addWidget(QLabel("Todas as Tags EXIF Detectadas:"))
        self.table_tags = QTableWidget()
        self.table_tags.setColumnCount(3)
        self.table_tags.setHorizontalHeaderLabels(["ID da Tag", "Nome do Metadado", "Valor"])
        self.table_tags.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_tags.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_tags.verticalHeader().setVisible(False)
        self.table_tags.setFixedHeight(240)
        layout.addWidget(self.table_tags)

        return w

    def _select_inspect_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem com EXIF",
            "",
            "Imagens (*.jpg *.jpeg *.tiff *.png *.webp)"
        )
        if not f:
            return

        self.txt_inspect_path.setText(f)
        p = Path(f)
        data = get_exif_info(p)

        self.lbl_camera.setText(f"{data['camera_make']} {data['camera_model']}".strip())
        self.lbl_date.setText(data["date_time"])
        self.lbl_exposure.setText(f"{data['exposure']} | {data['f_number']}")
        self.lbl_iso.setText(data["iso"])

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
        self.table_tags.setRowCount(len(raw))
        for r, (tid, tname, tval) in enumerate(raw):
            self.table_tags.setItem(r, 0, QTableWidgetItem(str(tid)))
            self.table_tags.setItem(r, 1, QTableWidgetItem(str(tname)))
            self.table_tags.setItem(r, 2, QTableWidgetItem(str(tval)))

    def _open_maps(self):
        if hasattr(self, "_current_maps_url") and self._current_maps_url:
            QDesktopServices.openUrl(QUrl(self._current_maps_url))

    def _build_batch_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Barra de Adição
        row_bar = QHBoxLayout()
        btn_add_files = QPushButton("Adicionar Imagens...")
        btn_add_files.clicked.connect(self._add_batch_files)
        row_bar.addWidget(btn_add_files)

        btn_add_folder = QPushButton("Adicionar Pasta...")
        btn_add_folder.clicked.connect(self._add_batch_folder)
        row_bar.addWidget(btn_add_folder)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self._clear_batch)
        row_bar.addWidget(btn_clear)
        row_bar.addStretch()
        layout.addLayout(row_bar)

        # Tabela de Arquivos
        self.table_batch = QTableWidget()
        self.table_batch.setColumnCount(3)
        self.table_batch.setHorizontalHeaderLabels(["Arquivo", "Status", "Pasta"])
        self.table_batch.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_batch.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_batch.verticalHeader().setVisible(False)
        self.table_batch.setFixedHeight(200)
        layout.addWidget(self.table_batch)

        self.lbl_batch_count = QLabel("Nenhum arquivo na lista.")
        layout.addWidget(self.lbl_batch_count)

        # Opções de Limpeza
        card_opt = QFrame()
        card_opt.setProperty("class", "card")
        l_opt = QVBoxLayout(card_opt)
        l_opt.setSpacing(8)

        self.cmb_batch_action = QComboBox()
        self.cmb_batch_action.addItems([
            "Remover Todos os Metadados (Anonimização Total)",
            "Remover Apenas Coordenadas de Localização (GPS)",
            "Renomear Arquivos pela Data de Captura (AAAA-MM-DD_HH-MM-SS)"
        ])
        l_opt.addWidget(QLabel("Ação em lote a executar:"))
        l_opt.addWidget(self.cmb_batch_action)

        self.chk_overwrite = QCheckBox("Substituir arquivos originais (sem criar cópias)")
        self.chk_overwrite.setChecked(False)
        l_opt.addWidget(self.chk_overwrite)
        layout.addWidget(card_opt)

        # Barra de Ação
        bar_run = QHBoxLayout()
        self.btn_run_batch = QPushButton("Executar Limpeza em Lote")
        self.btn_run_batch.setProperty("class", "primary")
        self.btn_run_batch.setFixedHeight(36)
        self.btn_run_batch.setEnabled(False)
        self.btn_run_batch.clicked.connect(self._run_batch_action)
        bar_run.addWidget(self.btn_run_batch)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        bar_run.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(bar_run)

        return w

    def _add_batch_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Fotos",
            "",
            "Fotos (*.jpg *.jpeg *.tiff *.png *.webp)"
        )
        if files:
            for f in files:
                p = Path(f)
                if p not in self.batch_files:
                    self.batch_files.append(p)
            self._refresh_batch_table()

    def _add_batch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta com Fotos")
        if folder:
            for root, _, files in os.walk(folder):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in (".jpg", ".jpeg", ".tiff", ".png", ".webp"):
                        p = Path(root) / f
                        if p not in self.batch_files:
                            self.batch_files.append(p)
            self._refresh_batch_table()

    def _clear_batch(self):
        self.batch_files.clear()
        self._refresh_batch_table()

    def _refresh_batch_table(self):
        self.table_batch.setRowCount(len(self.batch_files))
        self.lbl_batch_count.setText(f"{len(self.batch_files)} imagem(ns) carregada(s)")
        self.btn_run_batch.setEnabled(len(self.batch_files) > 0)

        for r, p in enumerate(self.batch_files):
            self.table_batch.setItem(r, 0, QTableWidgetItem(p.name))
            self.table_batch.setItem(r, 1, QTableWidgetItem("Pendente"))
            self.table_batch.setItem(r, 2, QTableWidgetItem(str(p.parent)))

    def _run_batch_action(self):
        if not self.batch_files:
            return

        action = self.cmb_batch_action.currentText()
        overwrite = self.chk_overwrite.isChecked()

        self.btn_run_batch.setEnabled(False)
        self.progress_bar.setValue(0)

        total = len(self.batch_files)

        def worker(ctx):
            success_count = 0
            for idx, p in enumerate(self.batch_files):
                try:
                    if action == "Renomear Arquivos pela Data de Captura (AAAA-MM-DD_HH-MM-SS)":
                        dt = get_exif_capture_date(p)
                        if dt:
                            new_name = f"{dt.strftime('%Y-%m-%d_%H-%M-%S')}{p.suffix.lower()}"
                            target = p.parent / new_name
                            if target != p and not target.exists():
                                p.rename(target)
                                success_count += 1
                        else:
                            success_count += 1
                    else:
                        gps_only = "Apenas Coordenadas" in action
                        if overwrite:
                            dst = p
                        else:
                            dst = p.parent / f"{p.stem}_limpo{p.suffix}"
                        strip_metadata(p, dst, remove_gps_only=gps_only)
                        success_count += 1
                except Exception:
                    pass

                ctx.send_progress(int(((idx + 1) / total) * 100), f"Processando item {idx+1}...")
            return success_count

        def on_task_progress(percent, _):
            self.progress_bar.setValue(percent)

        def on_done(count):
            self.btn_run_batch.setEnabled(True)
            self.progress_bar.setValue(100)
            for r in range(self.table_batch.rowCount()):
                self.table_batch.setItem(r, 1, QTableWidgetItem("Concluído"))
            QMessageBox.information(
                self,
                "Processamento Concluído",
                f"{count} imagem(ns) foram processadas com sucesso!"
            )

        def on_error(err):
            self.btn_run_batch.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha no processamento: {err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)
