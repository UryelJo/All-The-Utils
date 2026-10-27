"""
Ferramenta: Segurança e Senhas de PDF.
Interface moderna para proteção AES de documentos e desbloqueio permanente de arquivos conhecidos.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.pdf.security.logic import protect_pdf, unlock_pdf


@register
class PdfSecurityTool(Tool):
    id = "pdf.security"
    name = "Segurança e Senhas de PDF"
    category = "PDF"
    description = "Segurança de PDF: protege arquivos com senha de abertura ou permissões de impressão/cópia com criptografia AES, ou remove senhas de PDFs autorizados."
    keywords = ["pdf", "senha", "criptografia", "proteger", "segurança", "desbloquear", "remover senha", "aes"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Segurança e Senhas de PDF")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_protect_tab(), "Proteger com Senha")
        tabs.addTab(self._build_unlock_tab(), "Desbloquear / Remover Senha")
        main_layout.addWidget(tabs)

        return container

    # -------------------------------------------------------------------------
    # Aba 1: Proteger com Senha
    # -------------------------------------------------------------------------
    def _build_protect_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Arquivo de entrada
        grp_src = QGroupBox("Arquivo PDF de Entrada")
        grid_src = QGridLayout(grp_src)
        grid_src.addWidget(QLabel("PDF original:"), 0, 0)
        self.txt_protect_src = QLineEdit()
        self.txt_protect_src.setPlaceholderText("Selecione o PDF a ser protegido...")
        grid_src.addWidget(self.txt_protect_src, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_protect_src)
        grid_src.addWidget(btn_browse, 0, 2)
        layout.addWidget(grp_src)

        # Configurações de Senha
        grp_pwd = QGroupBox("Definição de Senha")
        grid_pwd = QGridLayout(grp_pwd)
        grid_pwd.setSpacing(8)

        grid_pwd.addWidget(QLabel("Senha de leitura:"), 0, 0)
        self.txt_pwd = QLineEdit()
        self.txt_pwd.setEchoMode(QLineEdit.Password)
        grid_pwd.addWidget(self.txt_pwd, 0, 1)

        btn_toggle_pwd = QPushButton("Mostrar")
        btn_toggle_pwd.clicked.connect(lambda: self._toggle_echo(self.txt_pwd, btn_toggle_pwd))
        grid_pwd.addWidget(btn_toggle_pwd, 0, 2)

        grid_pwd.addWidget(QLabel("Confirmar senha:"), 1, 0)
        self.txt_pwd_confirm = QLineEdit()
        self.txt_pwd_confirm.setEchoMode(QLineEdit.Password)
        grid_pwd.addWidget(self.txt_pwd_confirm, 1, 1)

        btn_toggle_confirm = QPushButton("Mostrar")
        btn_toggle_confirm.clicked.connect(lambda: self._toggle_echo(self.txt_pwd_confirm, btn_toggle_confirm))
        grid_pwd.addWidget(btn_toggle_confirm, 1, 2)

        layout.addWidget(grp_pwd)

        # Destino
        grp_dst = QGroupBox("Arquivo Protegido Resultante")
        grid_dst = QGridLayout(grp_dst)
        grid_dst.addWidget(QLabel("Salvar em:"), 0, 0)
        self.txt_protect_dst = QLineEdit()
        grid_dst.addWidget(self.txt_protect_dst, 0, 1)

        btn_browse_out = QPushButton("Procurar...")
        btn_browse_out.clicked.connect(self._on_browse_protect_dst)
        grid_dst.addWidget(btn_browse_out, 0, 2)
        layout.addWidget(grp_dst)

        # Ações
        act_box = QHBoxLayout()
        self.lbl_protect_status = QLabel("")
        act_box.addWidget(self.lbl_protect_status)
        act_box.addStretch()

        self.btn_run_protect = QPushButton("Criptografar PDF Agora")
        self.btn_run_protect.setProperty("class", "primary")
        self.btn_run_protect.clicked.connect(self._on_run_protect)
        act_box.addWidget(self.btn_run_protect)

        layout.addLayout(act_box)
        layout.addStretch()
        return tab

    def _toggle_echo(self, line_edit: QLineEdit, btn: QPushButton):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            btn.setText("Ocultar")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            btn.setText("Mostrar")

    def _on_browse_protect_src(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if file:
            p = Path(file)
            self.txt_protect_src.setText(str(p))
            if not self.txt_protect_dst.text():
                self.txt_protect_dst.setText(str(p.parent / f"{p.stem}_protegido.pdf"))

    def _on_browse_protect_dst(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar PDF Protegido", "documento_protegido.pdf", "Arquivos PDF (*.pdf)")
        if file:
            self.txt_protect_dst.setText(file)

    def _on_run_protect(self):
        src = self.txt_protect_src.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF válido para proteger.")
            return

        pwd = self.txt_pwd.text()
        pwd_c = self.txt_pwd_confirm.text()
        if not pwd:
            QMessageBox.warning(None, "Aviso", "A senha não pode estar em branco.")
            return
        if pwd != pwd_c:
            QMessageBox.warning(None, "Aviso", "A confirmação de senha não confere.")
            return

        dst = self.txt_protect_dst.text().strip()
        if not dst:
            QMessageBox.warning(None, "Aviso", "Informe o destino do arquivo PDF protegido.")
            return

        self.btn_run_protect.setEnabled(False)
        self.lbl_protect_status.setText("Criptografando documento...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Aplicando criptografia AES no documento...")
            res = protect_pdf(Path(src), Path(dst), user_password=pwd)
            ctx.progress(100, 100, "PDF criptografado com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run_protect.setEnabled(True)
            if exc:
                self.lbl_protect_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao criptografar: {exc}")
            else:
                self.lbl_protect_status.setText("Proteção aplicada com sucesso!")
                QMessageBox.information(None, "Sucesso", f"PDF criptografado com sucesso em:\n{result}")

        run_task(_work, on_done=_done)

    # -------------------------------------------------------------------------
    # Aba 2: Desbloquear / Remover Senha
    # -------------------------------------------------------------------------
    def _build_unlock_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grp_src = QGroupBox("Arquivo PDF Criptografado")
        grid_src = QGridLayout(grp_src)
        grid_src.addWidget(QLabel("PDF protegido:"), 0, 0)
        self.txt_unlock_src = QLineEdit()
        self.txt_unlock_src.setPlaceholderText("Selecione o PDF com senha...")
        grid_src.addWidget(self.txt_unlock_src, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_unlock_src)
        grid_src.addWidget(btn_browse, 0, 2)
        layout.addWidget(grp_src)

        grp_pwd = QGroupBox("Senha de Desbloqueio")
        grid_pwd = QGridLayout(grp_pwd)
        grid_pwd.addWidget(QLabel("Senha atual:"), 0, 0)
        self.txt_unlock_pwd = QLineEdit()
        self.txt_unlock_pwd.setEchoMode(QLineEdit.Password)
        grid_pwd.addWidget(self.txt_unlock_pwd, 0, 1)

        btn_toggle = QPushButton("Mostrar")
        btn_toggle.clicked.connect(lambda: self._toggle_echo(self.txt_unlock_pwd, btn_toggle))
        grid_pwd.addWidget(btn_toggle, 0, 2)
        layout.addWidget(grp_pwd)

        grp_dst = QGroupBox("Destino do PDF Desbloqueado")
        grid_dst = QGridLayout(grp_dst)
        grid_dst.addWidget(QLabel("Salvar em:"), 0, 0)
        self.txt_unlock_dst = QLineEdit()
        grid_dst.addWidget(self.txt_unlock_dst, 0, 1)

        btn_browse_dst = QPushButton("Procurar...")
        btn_browse_dst.clicked.connect(self._on_browse_unlock_dst)
        grid_dst.addWidget(btn_browse_dst, 0, 2)
        layout.addWidget(grp_dst)

        act_box = QHBoxLayout()
        self.lbl_unlock_status = QLabel("")
        act_box.addWidget(self.lbl_unlock_status)
        act_box.addStretch()

        self.btn_run_unlock = QPushButton("Remover Senha e Desbloquear")
        self.btn_run_unlock.setProperty("class", "primary")
        self.btn_run_unlock.clicked.connect(self._on_run_unlock)
        act_box.addWidget(self.btn_run_unlock)

        layout.addLayout(act_box)
        layout.addStretch()
        return tab

    def _on_browse_unlock_src(self):
        file, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF Protegido", "", "Arquivos PDF (*.pdf)")
        if file:
            p = Path(file)
            self.txt_unlock_src.setText(str(p))
            if not self.txt_unlock_dst.text():
                self.txt_unlock_dst.setText(str(p.parent / f"{p.stem}_desbloqueado.pdf"))

    def _on_browse_unlock_dst(self):
        file, _ = QFileDialog.getSaveFileName(None, "Salvar PDF Desbloqueado", "documento_desbloqueado.pdf", "Arquivos PDF (*.pdf)")
        if file:
            self.txt_unlock_dst.setText(file)

    def _on_run_unlock(self):
        src = self.txt_unlock_src.text().strip()
        if not src or not Path(src).is_file():
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF válido.")
            return

        pwd = self.txt_unlock_pwd.text()
        dst = self.txt_unlock_dst.text().strip()
        if not dst:
            QMessageBox.warning(None, "Aviso", "Informe o destino do arquivo desbloqueado.")
            return

        self.btn_run_unlock.setEnabled(False)
        self.lbl_unlock_status.setText("Descriptografando documento...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Removendo senha do documento...")
            res = unlock_pdf(Path(src), Path(dst), password=pwd)
            ctx.progress(100, 100, "PDF desbloqueado com sucesso!")
            return res

        def _done(result, exc):
            self.btn_run_unlock.setEnabled(True)
            if exc:
                self.lbl_unlock_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao desbloquear PDF: {exc}")
            else:
                self.lbl_unlock_status.setText("Documento livre de restrições gerado.")
                QMessageBox.information(None, "Sucesso", f"PDF desbloqueado com sucesso e salvo em:\n{result}")

        run_task(_work, on_done=_done)
