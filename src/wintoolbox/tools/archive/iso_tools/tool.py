"""
Interface gráfica da ferramenta Gerenciador de Imagens ISO e VHD (archive.iso_tools).
Permite montar, desmontar e extrair o conteúdo de imagens de disco virtuais no Windows.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.archive.iso_tools.logic import (
    mount_disk_image,
    dismount_disk_image,
    list_mounted_disk_images,
    extract_iso_contents,
)


@register
class IsoTools(Tool):
    id = "archive.iso_tools"
    name = "Ferramentas de Imagens ISO e VHD"
    description = "Gerenciador de imagens de disco: monta, desmonta e extrai o conteúdo de arquivos ISO, VHD e VHDX sem precisar de softwares adicionais."
    category = "Compactação"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs = QTabWidget()

        # Aba 1: Montar / Desmontar
        tab_mount = QWidget()
        mount_layout = QVBoxLayout(tab_mount)
        mount_layout.setSpacing(12)

        file_box = QHBoxLayout()
        lbl_file = QLabel("Arquivo de Imagem:")
        file_box.addWidget(lbl_file)

        self._edit_mount_file = QLineEdit()
        self._edit_mount_file.setPlaceholderText("Selecione um arquivo .iso, .vhd ou .vhdx...")
        file_box.addWidget(self._edit_mount_file)

        btn_browse_mount = QPushButton("Procurar...")
        btn_browse_mount.clicked.connect(self._on_browse_mount_file)
        file_box.addWidget(btn_browse_mount)
        mount_layout.addLayout(file_box)

        self._chk_read_only = QCheckBox("Montar como Somente Leitura (Recomendado para ISOs)")
        self._chk_read_only.setChecked(True)
        mount_layout.addWidget(self._chk_read_only)

        action_box = QHBoxLayout()
        self._btn_mount = QPushButton("Montar Imagem no Windows")
        self._btn_mount.clicked.connect(self._on_mount_click)
        action_box.addWidget(self._btn_mount)

        self._btn_dismount = QPushButton("Desmontar Imagem")
        self._btn_dismount.clicked.connect(self._on_dismount_click)
        action_box.addWidget(self._btn_dismount)
        action_box.addStretch()
        mount_layout.addLayout(action_box)

        self._lbl_mount_status = QLabel("Selecione um arquivo de imagem para montar.")
        self._lbl_mount_status.setStyleSheet("font-weight: bold;")
        mount_layout.addWidget(self._lbl_mount_status)
        mount_layout.addStretch()
        tabs.addTab(tab_mount, "Montar e Desmontar")

        # Aba 2: Imagens Montadas
        tab_list = QWidget()
        list_layout = QVBoxLayout(tab_list)
        list_layout.setSpacing(10)

        top_list_box = QHBoxLayout()
        btn_refresh = QPushButton("Atualizar Imagens Ativas")
        btn_refresh.clicked.connect(self._on_refresh_list)
        top_list_box.addWidget(btn_refresh)

        btn_dismount_sel = QPushButton("Desmontar Selecionada")
        btn_dismount_sel.clicked.connect(self._on_dismount_selected)
        top_list_box.addWidget(btn_dismount_sel)
        top_list_box.addStretch()
        list_layout.addLayout(top_list_box)

        self._table_mounted = QTableWidget(0, 3)
        self._table_mounted.setHorizontalHeaderLabels(["Caminho da Imagem", "Letra da Unidade", "Tipo"])
        self._table_mounted.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table_mounted.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table_mounted.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        list_layout.addWidget(self._table_mounted)
        tabs.addTab(tab_list, "Imagens Atualmente Montadas")

        # Aba 3: Extração Direta
        tab_extract = QWidget()
        ext_layout = QVBoxLayout(tab_extract)
        ext_layout.setSpacing(12)

        form = QFormLayout()
        self._edit_extract_iso = QLineEdit()
        self._edit_extract_iso.setPlaceholderText("Selecione a imagem ISO...")
        btn_browse_ext_iso = QPushButton("Procurar...")
        btn_browse_ext_iso.clicked.connect(self._on_browse_ext_iso)
        box_iso = QHBoxLayout()
        box_iso.addWidget(self._edit_extract_iso)
        box_iso.addWidget(btn_browse_ext_iso)
        form.addRow("Imagem ISO:", box_iso)

        self._edit_extract_dest = QLineEdit()
        self._edit_extract_dest.setPlaceholderText("Selecione a pasta de saída...")
        btn_browse_ext_dest = QPushButton("Procurar...")
        btn_browse_ext_dest.clicked.connect(self._on_browse_ext_dest)
        box_dest = QHBoxLayout()
        box_dest.addWidget(self._edit_extract_dest)
        box_dest.addWidget(btn_browse_ext_dest)
        form.addRow("Pasta de Destino:", box_dest)
        ext_layout.addLayout(form)

        self._btn_start_extract = QPushButton("Extrair Conteúdo Completo")
        self._btn_start_extract.clicked.connect(self._on_extract_click)
        ext_layout.addWidget(self._btn_start_extract)

        self._lbl_ext_status = QLabel("Pronto para extração.")
        ext_layout.addWidget(self._lbl_ext_status)
        ext_layout.addStretch()
        tabs.addTab(tab_extract, "Extrair Conteúdo")

        layout.addWidget(tabs)
        self._on_refresh_list()
        return widget

    def _on_browse_mount_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Imagem de Disco",
            "",
            "Imagens de Disco (*.iso *.vhd *.vhdx);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_mount_file.setText(path)

    def _on_browse_ext_iso(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Imagem ISO",
            "",
            "Imagens ISO (*.iso);;Todos os Arquivos (*.*)",
        )
        if path:
            self._edit_extract_iso.setText(path)

    def _on_browse_ext_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Destino")
        if path:
            self._edit_extract_dest.setText(path)

    def _on_mount_click(self) -> None:
        raw_path = self._edit_mount_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo de imagem.")
            return

        image_path = Path(raw_path)
        ro = self._chk_read_only.isChecked()
        self._lbl_mount_status.setText("Montando imagem de disco...")
        self._btn_mount.setEnabled(False)

        def worker():
            return mount_disk_image(image_path, read_only=ro)

        def on_done(res: Dict[str, Any]):
            self._btn_mount.setEnabled(True)
            drive = res.get("drive_letter")
            if drive:
                self._lbl_mount_status.setText(f"Imagem montada com sucesso na unidade {drive}!")
                self._lbl_mount_status.setStyleSheet("font-weight: bold; color: #28a745;")
            else:
                self._lbl_mount_status.setText("Imagem montada com sucesso.")
            self._on_refresh_list()

        def on_error(err: str):
            self._btn_mount.setEnabled(True)
            self._lbl_mount_status.setText(f"Erro ao montar: {err}")
            self._lbl_mount_status.setStyleSheet("font-weight: bold; color: #dc3545;")
            QMessageBox.critical(None, "Erro", f"Falha ao montar imagem: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_dismount_click(self) -> None:
        raw_path = self._edit_mount_file.text().strip()
        if not raw_path:
            QMessageBox.warning(None, "Aviso", "Selecione o arquivo de imagem para desmontar.")
            return

        image_path = Path(raw_path)
        self._lbl_mount_status.setText("Desmontando imagem...")
        self._btn_dismount.setEnabled(False)

        def worker():
            return dismount_disk_image(image_path)

        def on_done(res: Dict[str, Any]):
            self._btn_dismount.setEnabled(True)
            self._lbl_mount_status.setText("Imagem desmontada com sucesso.")
            self._lbl_mount_status.setStyleSheet("font-weight: bold;")
            self._on_refresh_list()

        def on_error(err: str):
            self._btn_dismount.setEnabled(True)
            self._lbl_mount_status.setText(f"Erro ao desmontar: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao desmontar imagem: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_refresh_list(self) -> None:
        def worker():
            return list_mounted_disk_images()

        def on_done(items: List[Dict[str, Any]]):
            self._table_mounted.setRowCount(len(items))
            for row, item in enumerate(items):
                self._table_mounted.setItem(row, 0, QTableWidgetItem(item.get("image_path", "")))
                self._table_mounted.setItem(row, 1, QTableWidgetItem(item.get("drive_letter") or "N/A"))
                self._table_mounted.setItem(row, 2, QTableWidgetItem(str(item.get("storage_type", ""))))

        TaskRunner.run(worker, on_success=on_done)

    def _on_dismount_selected(self) -> None:
        row = self._table_mounted.currentRow()
        if row < 0:
            QMessageBox.warning(None, "Aviso", "Selecione uma imagem na tabela para desmontar.")
            return

        item = self._table_mounted.item(row, 0)
        if not item or not item.text():
            return

        img_path = Path(item.text())

        def worker():
            return dismount_disk_image(img_path)

        def on_done(res: Dict[str, Any]):
            self._on_refresh_list()
            QMessageBox.information(None, "Sucesso", f"Imagem {img_path.name} desmontada.")

        def on_error(err: str):
            QMessageBox.critical(None, "Erro", f"Falha ao desmontar: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_extract_click(self) -> None:
        iso_str = self._edit_extract_iso.text().strip()
        dest_str = self._edit_extract_dest.text().strip()

        if not iso_str or not dest_str:
            QMessageBox.warning(None, "Aviso", "Informe o caminho do arquivo ISO e da pasta de saída.")
            return

        iso_path = Path(iso_str)
        dest_path = Path(dest_str)

        self._lbl_ext_status.setText("Extraindo conteúdo da imagem ISO...")
        self._btn_start_extract.setEnabled(False)

        def worker():
            return extract_iso_contents(iso_path, dest_path)

        def on_done(res: Dict[str, Any]):
            self._btn_start_extract.setEnabled(True)
            files = res.get("files_count", 0)
            self._lbl_ext_status.setText(f"Extração concluída com sucesso! {files} arquivos gravados.")
            QMessageBox.information(None, "Extração Concluída", f"{files} arquivos extraídos para:\n{dest_path}")

        def on_error(err: str):
            self._btn_start_extract.setEnabled(True)
            self._lbl_ext_status.setText(f"Erro na extração: {err}")
            QMessageBox.critical(None, "Erro", f"Falha na extração do ISO: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)
