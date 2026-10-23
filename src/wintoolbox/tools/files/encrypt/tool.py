"""
Ferramenta: Criptografia e Descriptografia Local de Arquivos com AES-256 (File Encryptor).
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import decrypt_file, encrypt_file, is_wintoolbox_encrypted


@register
class FileEncryptTool(Tool):
    id = "files.encrypt"
    name = "Criptografia Local de Arquivos (AES-256)"
    category = "Arquivos e Pastas"
    description = "Proteja arquivos confidenciais com criptografia AES-256-GCM e derivação de chave scrypt"
    keywords = ["criptografia", "encrypt", "decrypt", "aes", "segurança", "senha", "proteger", "arquivos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FileEncryptView(self, parent)


class FileEncryptView(QWidget):
    def __init__(self, tool: FileEncryptTool, parent: Optional[QWidget] = None):
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

        # ABA 1: Criptografar
        tab_enc = QWidget()
        l_enc = QVBoxLayout(tab_enc)
        l_enc.setSpacing(12)

        card_enc = QFrame()
        card_enc.setProperty("class", "card")
        l_cenc = QVBoxLayout(card_enc)
        l_cenc.setSpacing(10)

        r_f1 = QHBoxLayout()
        r_f1.addWidget(QLabel("Arquivo a ser protegido:"))
        self.txt_enc_in = QLineEdit()
        r_f1.addWidget(self.txt_enc_in, stretch=1)
        btn_b1 = QPushButton("Selecionar Arquivo...")
        btn_b1.clicked.connect(self._browse_enc_file)
        r_f1.addWidget(btn_b1)
        l_cenc.addLayout(r_f1)

        r_p1 = QHBoxLayout()
        r_p1.addWidget(QLabel("Senha mestra:"))
        self.txt_enc_pass1 = QLineEdit()
        self.txt_enc_pass1.setEchoMode(QLineEdit.Password)
        r_p1.addWidget(self.txt_enc_pass1, stretch=1)

        r_p1.addWidget(QLabel("Confirmar senha:"))
        self.txt_enc_pass2 = QLineEdit()
        self.txt_enc_pass2.setEchoMode(QLineEdit.Password)
        r_p1.addWidget(self.txt_enc_pass2, stretch=1)

        self.btn_show_pass_enc = QPushButton("Mostrar")
        self.btn_show_pass_enc.setCheckable(True)
        self.btn_show_pass_enc.toggled.connect(self._toggle_pass_enc)
        r_p1.addWidget(self.btn_show_pass_enc)
        l_cenc.addLayout(r_p1)

        self.chk_del_orig = QCheckBox("Excluir arquivo original permanentemente após criptografar com sucesso")
        l_cenc.addWidget(self.chk_del_orig)

        r_act1 = QHBoxLayout()
        self.btn_run_enc = QPushButton("Criptografar Arquivo com AES-256")
        self.btn_run_enc.setProperty("class", "primary")
        self.btn_run_enc.clicked.connect(self._start_encrypt)
        r_act1.addWidget(self.btn_run_enc)
        r_act1.addStretch()
        l_cenc.addLayout(r_act1)

        l_enc.addWidget(card_enc)
        l_enc.addStretch()
        tabs.addTab(tab_enc, "Criptografar Arquivo")

        # ABA 2: Descriptografar
        tab_dec = QWidget()
        l_dec = QVBoxLayout(tab_dec)
        l_dec.setSpacing(12)

        card_dec = QFrame()
        card_dec.setProperty("class", "card")
        l_cdec = QVBoxLayout(card_dec)
        l_cdec.setSpacing(10)

        r_f2 = QHBoxLayout()
        r_f2.addWidget(QLabel("Arquivo criptografado (.wtx_enc):"))
        self.txt_dec_in = QLineEdit()
        r_f2.addWidget(self.txt_dec_in, stretch=1)
        btn_b2 = QPushButton("Selecionar Arquivo...")
        btn_b2.clicked.connect(self._browse_dec_file)
        r_f2.addWidget(btn_b2)
        l_cdec.addLayout(r_f2)

        r_p2 = QHBoxLayout()
        r_p2.addWidget(QLabel("Senha de descriptografia:"))
        self.txt_dec_pass = QLineEdit()
        self.txt_dec_pass.setEchoMode(QLineEdit.Password)
        r_p2.addWidget(self.txt_dec_pass, stretch=1)

        self.btn_show_pass_dec = QPushButton("Mostrar")
        self.btn_show_pass_dec.setCheckable(True)
        self.btn_show_pass_dec.toggled.connect(self._toggle_pass_dec)
        r_p2.addWidget(self.btn_show_pass_dec)
        l_cdec.addLayout(r_p2)

        self.chk_del_enc = QCheckBox("Excluir arquivo criptografado após descriptografia bem-sucedida")
        l_cdec.addWidget(self.chk_del_enc)

        r_act2 = QHBoxLayout()
        self.btn_run_dec = QPushButton("Descriptografar Arquivo")
        self.btn_run_dec.setProperty("class", "primary")
        self.btn_run_dec.clicked.connect(self._start_decrypt)
        r_act2.addWidget(self.btn_run_dec)
        r_act2.addStretch()
        l_cdec.addLayout(r_act2)

        l_dec.addWidget(card_dec)
        l_dec.addStretch()
        tabs.addTab(tab_dec, "Descriptografar Arquivo")

        layout.addWidget(tabs)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Pronto para criptografia e descriptografia local.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _toggle_pass_enc(self, checked: bool):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.txt_enc_pass1.setEchoMode(mode)
        self.txt_enc_pass2.setEchoMode(mode)
        self.btn_show_pass_enc.setText("Ocultar" if checked else "Mostrar")

    def _toggle_pass_dec(self, checked: bool):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.txt_dec_pass.setEchoMode(mode)
        self.btn_show_pass_dec.setText("Ocultar" if checked else "Mostrar")

    def _browse_enc_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Criptografar")
        if f:
            self.txt_enc_in.setText(f)

    def _browse_dec_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo Criptografado", filter="Arquivos Criptografados (*.wtx_enc *.enc);;Todos os Arquivos (*.*)")
        if f:
            self.txt_dec_in.setText(f)

    def _start_encrypt(self):
        in_path_str = self.txt_enc_in.text().strip()
        src = Path(in_path_str)
        if not src.is_file():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo válido para criptografar.")
            return

        pass1 = self.txt_enc_pass1.text()
        pass2 = self.txt_enc_pass2.text()
        if not pass1:
            QMessageBox.warning(self, "Aviso", "Digite uma senha para proteger o arquivo.")
            return
        if pass1 != pass2:
            QMessageBox.warning(self, "Aviso", "As duas senhas digitadas não coincidem.")
            return

        dst = src.with_suffix(f"{src.suffix}.wtx_enc")
        del_orig = self.chk_del_orig.isChecked()

        self.btn_run_enc.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("Criptografando com AES-256-GCM...")

        def worker(ctx):
            return encrypt_file(
                src_path=src,
                dst_path=dst,
                password=pass1,
                delete_original=del_orig,
                progress_cb=ctx.on_progress
            )

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(msg)

        def on_done(res_path: Path):
            self.btn_run_enc.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.lbl_status.setText("Arquivo criptografado com sucesso!")
            QMessageBox.information(
                self,
                "Criptografia Concluída",
                f"O arquivo foi protegido com sucesso com AES-256!\n\nSalvo em:\n{res_path}"
            )
            self.txt_enc_pass1.clear()
            self.txt_enc_pass2.clear()

        def on_err(err_msg: str):
            self.btn_run_enc.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.lbl_status.setText("Falha na criptografia.")
            QMessageBox.critical(self, "Erro", f"Falha ao criptografar arquivo:\n{err_msg}")

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done, on_error=on_err)

    def _start_decrypt(self):
        in_path_str = self.txt_dec_in.text().strip()
        src = Path(in_path_str)
        if not src.is_file():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo criptografado válido.")
            return

        password = self.txt_dec_pass.text()
        if not password:
            QMessageBox.warning(self, "Aviso", "Digite a senha de descriptografia.")
            return

        # Nome de saída restaurado
        if src.name.endswith(".wtx_enc"):
            dst_name = src.name[:-8]
        elif src.name.endswith(".enc"):
            dst_name = src.name[:-4]
        else:
            dst_name = f"restaurado_{src.name}"

        dst = src.parent / dst_name
        del_enc = self.chk_del_enc.isChecked()

        self.btn_run_dec.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("Descriptografando arquivo...")

        def worker(ctx):
            return decrypt_file(
                src_path=src,
                dst_path=dst,
                password=password,
                delete_encrypted=del_enc,
                progress_cb=ctx.on_progress
            )

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(msg)

        def on_done(res_path: Path):
            self.btn_run_dec.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.lbl_status.setText("Arquivo descriptografado com sucesso!")
            QMessageBox.information(
                self,
                "Descriptografia Concluída",
                f"Arquivo restaurado com integridade verificada!\n\nSalvo em:\n{res_path}"
            )
            self.txt_dec_pass.clear()

        def on_err(err_msg: str):
            self.btn_run_dec.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.lbl_status.setText("Falha na descriptografia.")
            QMessageBox.critical(self, "Erro de Descriptografia", f"{err_msg}")

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done, on_error=on_err)
