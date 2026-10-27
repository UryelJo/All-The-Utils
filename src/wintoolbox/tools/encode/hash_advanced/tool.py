"""
Interface gráfica da ferramenta Hashes Avançados e Verificação em Lote (encode.hash_advanced).
Permite calcular hashes BLAKE2, SHA3, SHA-256/512, MD5, CRC32,
gerar arquivos de manifesto (.sha256, .sfv) e verificar a integridade de diretórios inteiros.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.encode.hash_advanced.logic import (
    compute_file_hash_stream,
    generate_manifest_content,
    verify_manifest_file,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class HashAdvancedTool(Tool):
    id = "encode.hash_advanced"
    name = "Hashes Avançados e Verificador de Manifestos"
    category = "Codificação e Hash"
    description = (
        "Calcula hashes criptográficos modernos (BLAKE2, SHA-3, SHA-256, CRC32), "
        "gera manifestos de verificação (.sha256, .sfv) e valida a integridade de lotes de arquivos."
    )
    keywords = ["hash", "sha256", "sha3", "blake2", "sfv", "manifesto", "checksum", "integridade", "lote"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return HashAdvancedView(self, parent)


class HashAdvancedView(QWidget):
    def __init__(self, tool: HashAdvancedTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_files_for_gen: List[Path] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Abas
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_verify_tab(), "Verificar Manifesto (.sha256 / .sfv)")
        self._tabs.addTab(self._build_generate_tab(), "Gerar Manifesto em Lote")
        root_layout.addWidget(self._tabs)

    def _build_verify_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Barra de seleção de manifesto
        top_bar = QHBoxLayout()
        self._txt_manifest_path = QLineEdit()
        self._txt_manifest_path.setPlaceholderText("Selecione um arquivo de manifesto (.sha256, .sha512, .sfv, .md5)...")
        self._txt_manifest_path.setReadOnly(True)
        top_bar.addWidget(self._txt_manifest_path)

        btn_browse = QPushButton("Abrir Manifesto...")
        btn_browse.clicked.connect(self._on_browse_manifest)
        top_bar.addWidget(btn_browse)

        self._btn_verify = QPushButton("Verificar Integridade")
        self._btn_verify.setEnabled(False)
        self._btn_verify.clicked.connect(self._run_manifest_verification)
        top_bar.addWidget(self._btn_verify)

        layout.addLayout(top_bar)

        # Resumo de integridade
        self._lbl_verify_summary = QLabel("Nenhum manifesto carregado.")
        self._lbl_verify_summary.setStyleSheet("font-size: 12px; color: #4b5563; font-weight: bold;")
        layout.addWidget(self._lbl_verify_summary)

        # Tabela de Resultados usando DataTableView
        cols = [
            Column("status", "Status", width=90),
            Column("filename", "Arquivo", width=220),
            Column("expected", "Hash Esperado", width=190),
            Column("computed", "Hash Calculado", width=190),
            Column("details", "Diagnóstico", width=240),
        ]
        self._verify_table = DataTableView(cols, key="filename", parent=self)
        layout.addWidget(self._verify_table)

        return widget

    def _build_generate_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # Controles
        ctrl_bar = QHBoxLayout()
        btn_add_files = QPushButton("Selecionar Arquivos...")
        btn_add_files.clicked.connect(self._on_select_files_for_gen)
        ctrl_bar.addWidget(btn_add_files)

        ctrl_bar.addWidget(QLabel("Algoritmo:"))
        self._combo_alg = QComboBox()
        self._combo_alg.addItems(["SHA-256", "SHA-512", "SHA3-256", "BLAKE2b", "MD5", "CRC32 (SFV)"])
        ctrl_bar.addWidget(self._combo_alg)

        btn_generate = QPushButton("Calcular e Gerar")
        btn_generate.clicked.connect(self._on_generate_manifest)
        ctrl_bar.addWidget(btn_generate)

        ctrl_bar.addStretch()
        layout.addLayout(ctrl_bar)

        self._lbl_gen_status = QLabel("Nenhum arquivo selecionado.")
        self._lbl_gen_status.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(self._lbl_gen_status)

        # Pré-visualização do conteúdo gerado
        self._txt_manifest_output = QPlainTextEdit()
        self._txt_manifest_output.setFont(QFont("Consolas", 9))
        self._txt_manifest_output.setPlaceholderText("O conteúdo gerado do manifesto aparecerá aqui...")
        layout.addWidget(self._txt_manifest_output)

        # Ações de salvamento
        act_bar = QHBoxLayout()
        btn_copy = QPushButton("Copiar Conteúdo")
        btn_copy.clicked.connect(self._copy_manifest_output)
        act_bar.addWidget(btn_copy)

        btn_save = QPushButton("Salvar Arquivo de Manifesto...")
        btn_save.clicked.connect(self._save_manifest_file)
        act_bar.addWidget(btn_save)

        act_bar.addStretch()
        layout.addLayout(act_bar)

        return widget

    def _on_browse_manifest(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo de Manifesto", "", "Manifestos (*.sha256 *.sha512 *.sfv *.md5 *.txt);;Todos (*.*)"
        )
        if not fpath:
            return
        self._txt_manifest_path.setText(fpath)
        self._btn_verify.setEnabled(True)
        self._run_manifest_verification()

    def _run_manifest_verification(self):
        mpath = self._txt_manifest_path.text()
        if not mpath or not Path(mpath).is_file():
            return

        self._lbl_verify_summary.setText("Calculando hashes e verificando integridade...")
        self._runner.run(
            verify_manifest_file,
            Path(mpath),
            on_success=self._on_verify_success,
            on_error=self._on_verify_error,
        )

    def _on_verify_success(self, results: List[dict]):
        self._verify_table.set_records(results)
        total = len(results)
        ok_count = sum(1 for r in results if r.get("status") == "OK")
        fail_count = sum(1 for r in results if r.get("status") == "FALHOU")
        missing_count = sum(1 for r in results if r.get("status") == "AUSENTE")

        summary_msg = f"{total} arquivos avaliados: {ok_count} Válidos (OK), {fail_count} Corrompidos, {missing_count} Ausentes."
        if fail_count > 0 or missing_count > 0:
            self._lbl_verify_summary.setStyleSheet("color: #b91c1c; font-weight: bold;")
        else:
            self._lbl_verify_summary.setStyleSheet("color: #047857; font-weight: bold;")
        self._lbl_verify_summary.setText(summary_msg)

    def _on_verify_error(self, exc: Exception):
        QMessageBox.critical(self, "Erro de Verificação", f"Falha ao verificar manifesto: {exc}")
        self._lbl_verify_summary.setText("Erro durante a verificação.")

    def _on_select_files_for_gen(self):
        fpaths, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para o Manifesto")
        if not fpaths:
            return
        self._selected_files_for_gen = [Path(p) for p in fpaths]
        self._lbl_gen_status.setText(f"{len(self._selected_files_for_gen)} arquivo(s) selecionado(s)")

    def _on_generate_manifest(self):
        if not self._selected_files_for_gen:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione ao menos um arquivo.")
            return

        alg_raw = self._combo_alg.currentText().split()[0]
        alg_map = {
            "SHA-256": "sha256",
            "SHA-512": "sha512",
            "SHA3-256": "sha3_256",
            "BLAKE2b": "blake2b",
            "MD5": "md5",
            "CRC32": "crc32",
        }
        alg = alg_map.get(alg_raw, "sha256")

        self._lbl_gen_status.setText("Calculando hashes em lote...")
        self._runner.run(
            generate_manifest_content,
            self._selected_files_for_gen,
            alg,
            on_success=self._on_generate_success,
            on_error=self._on_verify_error,
        )

    def _on_generate_success(self, manifest_text: str):
        self._txt_manifest_output.setPlainText(manifest_text)
        self._lbl_gen_status.setText(f"Manifesto gerado com sucesso ({len(manifest_text.splitlines())} registros)!")

    def _copy_manifest_output(self):
        txt = self._txt_manifest_output.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def _save_manifest_file(self):
        txt = self._txt_manifest_output.toPlainText()
        if not txt:
            return
        fpath, _ = QFileDialog.getSaveFileName(self, "Salvar Manifesto", "checksums.sha256", "Manifestos (*.sha256 *.sfv *.txt)")
        if not fpath:
            return
        Path(fpath).write_text(txt, encoding="utf-8")
        QMessageBox.information(self, "Sucesso", "Manifesto salvo com sucesso!")
