"""
Ferramenta: Gerador de Hash e Checksum (Texto e Arquivos).
Suporta MD5, SHA-1, SHA-256, SHA-512, SHA3-256, CRC32 e HMAC.
"""
import hashlib
import hmac
import zlib
from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import compare_hashes, compute_file_hash, compute_text_hashes

@register
class CryptoHashTool(Tool):
    id = "encode.crypto_hash"
    name = "Gerador de Hash e Checksum"
    category = "Codificação e Hash"
    description = "Calcula hashes MD5, SHA-1, SHA-256, SHA-512, CRC32 e HMAC de textos e arquivos"
    keywords = ["hash", "md5", "sha256", "sha1", "sha512", "crc32", "checksum", "hmac", "integridade"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CryptoHashView(self, parent)

class CryptoHashView(QWidget):
    def __init__(self, tool: CryptoHashTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
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

        # ABA 1: Hash de Texto
        tab_text = QWidget()
        l_text = QVBoxLayout(tab_text)
        l_text.setSpacing(10)

        l_text.addWidget(QLabel("Texto para Cálculo do Hash:"))
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Digite ou cole o texto aqui...")
        self.txt_input.setFixedHeight(110)
        self.txt_input.textChanged.connect(self._recalc_text_hashes)
        l_text.addWidget(self.txt_input)

        row_hmac = QHBoxLayout()
        row_hmac.addWidget(QLabel("Chave Secreta HMAC (Opcional):"))
        self.txt_secret = QLineEdit()
        self.txt_secret.setPlaceholderText("Deixe em branco para hash comum sem HMAC")
        self.txt_secret.textChanged.connect(self._recalc_text_hashes)
        row_hmac.addWidget(self.txt_secret, stretch=1)
        l_text.addLayout(row_hmac)

        # Container dos resultados de Hash
        card_results = QFrame()
        card_results.setProperty("class", "card")
        self.l_results = QVBoxLayout(card_results)
        self.l_results.setSpacing(8)

        self.hash_fields = {}
        for alg in ["MD5", "SHA-1", "SHA-256", "SHA-512", "CRC32", "HMAC-SHA256"]:
            row_h = QHBoxLayout()
            lbl_alg = QLabel(f"{alg}:")
            lbl_alg.setFixedWidth(110)
            lbl_alg.setStyleSheet("font-weight: 600;")
            row_h.addWidget(lbl_alg)

            val_field = QLineEdit()
            val_field.setReadOnly(True)
            row_h.addWidget(val_field, stretch=1)

            btn_cp = QPushButton("Copiar")
            btn_cp.clicked.connect(lambda _, f=val_field: self._copy_field(f))
            row_h.addWidget(btn_cp)

            self.l_results.addLayout(row_h)
            self.hash_fields[alg] = val_field

        l_text.addWidget(card_results)
        l_text.addStretch()
        tabs.addTab(tab_text, "Hash de Texto")

        # ABA 2: Checksum de Arquivo
        tab_file = QWidget()
        l_file = QVBoxLayout(tab_file)
        l_file.setSpacing(12)

        card_f = QFrame()
        card_f.setProperty("class", "card")
        l_cf = QVBoxLayout(card_f)
        l_cf.setSpacing(10)

        row_f1 = QHBoxLayout()
        row_f1.addWidget(QLabel("Arquivo Selecionado:"))
        self.txt_file_path = QLineEdit()
        self.txt_file_path.setReadOnly(True)
        self.txt_file_path.setPlaceholderText("Nenhum arquivo selecionado...")
        row_f1.addWidget(self.txt_file_path, stretch=1)

        btn_browse = QPushButton("Selecionar Arquivo...")
        btn_browse.clicked.connect(self._browse_file)
        row_f1.addWidget(btn_browse)
        l_cf.addLayout(row_f1)

        row_f2 = QHBoxLayout()
        row_f2.addWidget(QLabel("Algoritmo:"))
        self.cmb_file_alg = QComboBox()
        self.cmb_file_alg.addItems(["SHA-256", "SHA-512", "MD5", "SHA-1", "CRC32"])
        row_f2.addWidget(self.cmb_file_alg)

        self.btn_calc_file = QPushButton("Calcular Checksum")
        self.btn_calc_file.setProperty("class", "primary")
        self.btn_calc_file.setEnabled(False)
        self.btn_calc_file.clicked.connect(self._calculate_file_checksum)
        row_f2.addWidget(self.btn_calc_file)
        row_f2.addStretch()
        l_cf.addLayout(row_f2)

        self.prog_file = QProgressBar()
        self.prog_file.setRange(0, 100)
        self.prog_file.setValue(0)
        self.prog_file.setFixedHeight(6)
        self.prog_file.setTextVisible(False)
        l_cf.addWidget(self.prog_file)

        row_f3 = QHBoxLayout()
        row_f3.addWidget(QLabel("Hash Calculado:"))
        self.txt_file_hash = QLineEdit()
        self.txt_file_hash.setReadOnly(True)
        self.txt_file_hash.setStyleSheet("font-weight: 600; color: #0078d4;")
        row_f3.addWidget(self.txt_file_hash, stretch=1)

        btn_cp_file = QPushButton("Copiar")
        btn_cp_file.clicked.connect(lambda: self._copy_field(self.txt_file_hash))
        row_f3.addWidget(btn_cp_file)
        l_cf.addLayout(row_f3)

        # Comparador de Hash
        row_cmp = QHBoxLayout()
        row_cmp.addWidget(QLabel("Comparar com Hash Esperado:"))
        self.txt_expected_hash = QLineEdit()
        self.txt_expected_hash.setPlaceholderText("Cole o hash oficial aqui para validar integridade...")
        self.txt_expected_hash.textChanged.connect(self._compare_hashes)
        row_cmp.addWidget(self.txt_expected_hash, stretch=1)
        l_cf.addLayout(row_cmp)

        self.lbl_cmp_status = QLabel("Aguardando cálculo...")
        self.lbl_cmp_status.setStyleSheet("font-weight: 600;")
        l_cf.addWidget(self.lbl_cmp_status)

        l_file.addWidget(card_f)
        l_file.addStretch()
        tabs.addTab(tab_file, "Checksum de Arquivo")

        layout.addWidget(tabs)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._recalc_text_hashes()

    def _recalc_text_hashes(self):
        text = self.txt_input.toPlainText()
        secret = self.txt_secret.text()
        hashes = compute_text_hashes(text, secret)
        for alg, field in self.hash_fields.items():
            field.setText(hashes.get(alg, ""))

    def _copy_field(self, field: QLineEdit):
        text = field.text().strip()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Hash copiado para a área de transferência!")

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Hash")
        if path:
            self.txt_file_path.setText(path)
            self.btn_calc_file.setEnabled(True)
            self.txt_file_hash.clear()
            self.lbl_cmp_status.setText("Pronto para calcular.")

    def _calculate_file_checksum(self):
        path_str = self.txt_file_path.text().strip()
        if not path_str:
            return
        file_path = Path(path_str)
        alg = self.cmb_file_alg.currentText()

        self.btn_calc_file.setEnabled(False)
        self.prog_file.setValue(0)
        self.lbl_cmp_status.setText("Calculando hash em segundo plano...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")
            return compute_file_hash(file_path, alg, on_progress)

        def on_task_progress(percent, _):
            self.prog_file.setValue(percent)

        def on_done(hash_val):
            self.btn_calc_file.setEnabled(True)
            self.prog_file.setValue(100)
            self.txt_file_hash.setText(hash_val)
            self._compare_hashes()

        def on_error(err):
            self.btn_calc_file.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha ao calcular hash:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _compare_hashes(self):
        calculated = self.txt_file_hash.text().strip()
        expected = self.txt_expected_hash.text().strip()

        if not calculated or not expected:
            self.lbl_cmp_status.setText("Cole o hash esperado para comparação automática.")
            self.lbl_cmp_status.setStyleSheet("font-weight: 500; color: #aaa;")
            return

        if compare_hashes(calculated, expected):
            self.lbl_cmp_status.setText("[VÁLIDO] Os hashes são idênticos! O arquivo é autêntico.")
            self.lbl_cmp_status.setStyleSheet("font-weight: 600; color: #7ee787;")
        else:
            self.lbl_cmp_status.setText("[DIVERGENTE] Os hashes não coincidem! O arquivo pode estar corrompido.")
            self.lbl_cmp_status.setStyleSheet("font-weight: 600; color: #ffa198;")
