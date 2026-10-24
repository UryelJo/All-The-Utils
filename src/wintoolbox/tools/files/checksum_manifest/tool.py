"""
Interface gráfica do Gerador e Verificador de Manifesto de Checksums de Pastas.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.files.checksum_manifest.logic import (
    generate_folder_manifest, verify_manifest_file
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("files.checksum_manifest.ui")


@register
class ChecksumManifestTool(Tool):
    id = "files.checksum_manifest"
    name = "Manifesto de Checksums (.sha256)"
    category = "Arquivos e Pastas"
    description = "Geração e validação em lote de integridade de pastas inteiras via arquivos de manifesto sha256/md5"
    keywords = ["checksum", "sha256", "md5", "manifesto", "integridade", "hash", "verificar", "sha256sum"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ChecksumManifestView(self, parent)


class ChecksumManifestView(QWidget):
    def __init__(self, tool: ChecksumManifestTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._last_manifest_text: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        self.tabs = QTabWidget()
        self._setup_generate_tab()
        self._setup_verify_tab()
        layout.addWidget(self.tabs, stretch=1)

    def _setup_generate_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        # Barra de seleção de pasta
        bar = QHBoxLayout()
        self.txt_folder = QLineEdit()
        self.txt_folder.setPlaceholderText("Selecione a pasta para gerar o manifesto...")
        bar.addWidget(self.txt_folder, stretch=1)

        btn_browse = QPushButton("Procurar Pasta...")
        btn_browse.clicked.connect(self._browse_folder)
        bar.addWidget(btn_browse)

        self.combo_algo = QComboBox()
        self.combo_algo.addItem("SHA-256", "sha256")
        self.combo_algo.addItem("MD5", "md5")
        bar.addWidget(self.combo_algo)

        self.chk_recursive = QCheckBox("Recursivo")
        self.chk_recursive.setChecked(True)
        bar.addWidget(self.chk_recursive)

        self.btn_generate = QPushButton("Gerar e Salvar Manifesto")
        self.btn_generate.setProperty("accent", True)
        self.btn_generate.clicked.connect(self._generate_manifest_async)
        bar.addWidget(self.btn_generate)

        lay.addLayout(bar)

        self.table_gen = QTableWidget(0, 2)
        self.table_gen.setHorizontalHeaderLabels(["Arquivo Relativo", "Hash Criptográfico"])
        self.table_gen.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_gen.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        lay.addWidget(self.table_gen, stretch=1)

        self.lbl_gen_status = QLabel("Pronto para gerar manifesto.")
        lay.addWidget(self.lbl_gen_status)

        self.tabs.addTab(tab, "Gerar Manifesto de Pasta")

    def _setup_verify_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        self.txt_manifest_path = QLineEdit()
        self.txt_manifest_path.setPlaceholderText("Selecione o arquivo .sha256 ou .md5 para verificar...")
        bar.addWidget(self.txt_manifest_path, stretch=1)

        btn_browse_m = QPushButton("Procurar Arquivo...")
        btn_browse_m.clicked.connect(self._browse_manifest_file)
        bar.addWidget(btn_browse_m)

        self.btn_verify = QPushButton("Verificar Integridade")
        self.btn_verify.setProperty("accent", True)
        self.btn_verify.clicked.connect(self._verify_manifest_async)
        bar.addWidget(self.btn_verify)

        lay.addLayout(bar)

        self.table_verify = QTableWidget(0, 4)
        self.table_verify.setHorizontalHeaderLabels(["Arquivo", "Status", "Hash Esperado", "Hash Atual"])
        self.table_verify.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_verify.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_verify.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_verify.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        lay.addWidget(self.table_verify, stretch=1)

        self.lbl_verify_status = QLabel("Selecione um manifesto e clique em Verificar.")
        lay.addWidget(self.lbl_verify_status)

        self.tabs.addTab(tab, "Verificar Integridade")

    def _browse_folder(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Manifesto", "")
        if p:
            self.txt_folder.setText(p)

    def _browse_manifest_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo de Manifesto", "", "Manifestos (*.sha256 *.md5 *.txt);;Todos os Arquivos (*.*)")
        if p:
            self.txt_manifest_path.setText(p)

    def _generate_manifest_async(self) -> None:
        f_str = self.txt_folder.text().strip()
        if not f_str or not Path(f_str).is_dir():
            show_toast(self, "Selecione uma pasta válida primeiro.", is_error=True)
            return

        folder = Path(f_str)
        algo = self.combo_algo.currentData()
        rec = self.chk_recursive.isChecked()

        self.btn_generate.setEnabled(False)
        self.lbl_gen_status.setText("Calculando hashes dos arquivos...")

        def _worker():
            return generate_folder_manifest(folder, algo=algo, recursive=rec)

        def _on_done(result):
            items, text = result
            self.btn_generate.setEnabled(True)
            self._last_manifest_text = text

            self.table_gen.setRowCount(len(items))
            for row, it in enumerate(items):
                self.table_gen.setItem(row, 0, QTableWidgetItem(it["file"]))
                self.table_gen.setItem(row, 1, QTableWidgetItem(it["hash"]))

            # Salva o arquivo de manifesto na própria pasta
            ext = ".sha256" if algo == "sha256" else ".md5"
            save_dest = folder / f"manifest_{algo}{ext}"
            save_dest.write_text(text, encoding="utf-8")

            self.lbl_gen_status.setText(f"{len(items)} arquivos indexados. Manifesto salvo em: {save_dest.name}")
            show_toast(self, f"Manifesto gerado e salvo com sucesso ({len(items)} arquivos)!")

        def _on_error(err):
            self.btn_generate.setEnabled(True)
            self.lbl_gen_status.setText("Erro ao gerar manifesto.")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _verify_manifest_async(self) -> None:
        m_str = self.txt_manifest_path.text().strip()
        if not m_str or not Path(m_str).is_file():
            show_toast(self, "Selecione um arquivo de manifesto existente.", is_error=True)
            return

        manifest_file = Path(m_str)
        self.btn_verify.setEnabled(False)
        self.lbl_verify_status.setText("Verificando integridade de cada arquivo...")

        def _worker():
            return verify_manifest_file(manifest_file)

        def _on_done(results: List[Dict[str, Any]]):
            self.btn_verify.setEnabled(True)
            self.table_verify.setRowCount(len(results))
            ok_count = 0
            err_count = 0

            for row, r in enumerate(results):
                self.table_verify.setItem(row, 0, QTableWidgetItem(r["file"]))

                st_item = QTableWidgetItem(r["status"])
                if r["status"] == "OK":
                    st_item.setForeground(Qt.green)
                    ok_count += 1
                else:
                    st_item.setForeground(Qt.red)
                    err_count += 1
                self.table_verify.setItem(row, 1, st_item)

                self.table_verify.setItem(row, 2, QTableWidgetItem(r["expected"]))
                self.table_verify.setItem(row, 3, QTableWidgetItem(r["actual"]))

            self.lbl_verify_status.setText(f"Concluído: {ok_count} OK, {err_count} com falhas/ausentes.")
            if err_count == 0:
                show_toast(self, "Todos os arquivos foram verificados com 100% de integridade!")
            else:
                show_toast(self, f"Atenção: {err_count} arquivo(s) com divergência de hash!", is_error=True)

        def _on_error(err):
            self.btn_verify.setEnabled(True)
            self.lbl_verify_status.setText("Erro ao verificar manifesto.")
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)
