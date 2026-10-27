"""
Interface gráfica Fluent da ferramenta Gerador de Chaves SSH e Criptográficas.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.keygen.logic import (
    generate_key_pair,
    GeneratedKeyPair,
)


@register
class KeygenTool(Tool):
    """Ferramenta para geração de pares de chaves assimétricas SSH (Ed25519, RSA, ECDSA)."""
    id = "encode.keygen"
    title = "Gerador de Chaves SSH"
    category = "Codificação e Hash"
    description = (
        "Gera pares de chaves criptográficas assimétricas Ed25519, RSA (2048/4096 bits) e ECDSA "
        "nos formatos OpenSSH e PEM, com proteção por senha e visualização de fingerprints SHA-256 e MD5."
    )
    icon = "Key"

    def __init__(self) -> None:
        super().__init__()
        self._current_key_pair: GeneratedKeyPair | None = None

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Gerador de Pares de Chaves SSH e Criptográficas")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Crie chaves de alta segurança para autenticação em servidores SSH, GitHub, GitLab e AWS. "
            "Recomendamos o algoritmo moderno Ed25519 por sua velocidade e tamanho compacto de chave."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Configurações de Geração
        cfg_frame = QFrame()
        cfg_frame.setFrameShape(QFrame.Shape.StyledPanel)
        cfg_layout = QHBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(10, 10, 10, 10)
        cfg_layout.setSpacing(14)

        cfg_layout.addWidget(QLabel("Algoritmo:"))
        self.combo_algo = QComboBox()
        self.combo_algo.addItem("Ed25519 (Recomendado)", "ed25519")
        self.combo_algo.addItem("RSA 4096 bits", "rsa4096")
        self.combo_algo.addItem("RSA 2048 bits", "rsa2048")
        self.combo_algo.addItem("ECDSA P-256", "ecdsa_p256")
        cfg_layout.addWidget(self.combo_algo)

        cfg_layout.addWidget(QLabel("Comentário:"))
        self.edit_comment = QLineEdit("usuario@WinToolbox")
        cfg_layout.addWidget(self.edit_comment)

        cfg_layout.addWidget(QLabel("Senha (Opcional):"))
        self.edit_pass = QLineEdit()
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass.setPlaceholderText("Deixe vazio para sem senha...")
        cfg_layout.addWidget(self.edit_pass)

        self.btn_generate = QPushButton("Gerar Novo Par de Chaves")
        self.btn_generate.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_generate.clicked.connect(self._on_generate)
        cfg_layout.addWidget(self.btn_generate)

        layout.addWidget(cfg_frame)

        # Card de Impressões Digitais (Fingerprints)
        grp_fp = QGroupBox("Impressões Digitais da Chave Pública (Fingerprints)")
        v_fp = QVBoxLayout(grp_fp)
        v_fp.setSpacing(6)

        row_sha = QHBoxLayout()
        row_sha.addWidget(QLabel("SHA-256 (Padrão OpenSSH):"))
        self.lbl_fp_sha256 = QLabel("-")
        self.lbl_fp_sha256.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #0078D4;")
        row_sha.addWidget(self.lbl_fp_sha256, 1)
        btn_copy_sha = QPushButton("Copiar")
        btn_copy_sha.clicked.connect(lambda: self._copy_text(self.lbl_fp_sha256.text()))
        row_sha.addWidget(btn_copy_sha)
        v_fp.addLayout(row_sha)

        row_md5 = QHBoxLayout()
        row_md5.addWidget(QLabel("MD5 (Padrão Legado):"))
        self.lbl_fp_md5 = QLabel("-")
        self.lbl_fp_md5.setStyleSheet("font-family: Consolas, monospace;")
        row_md5.addWidget(self.lbl_fp_md5, 1)
        btn_copy_md5 = QPushButton("Copiar")
        btn_copy_md5.clicked.connect(lambda: self._copy_text(self.lbl_fp_md5.text()))
        row_md5.addWidget(btn_copy_md5)
        v_fp.addLayout(row_md5)

        layout.addWidget(grp_fp)

        # Tabs com Chave Pública e Chave Privada
        tabs = QTabWidget()

        # Tab Chave Pública
        tab_pub = QWidget()
        v_pub = QVBoxLayout(tab_pub)
        v_pub.setSpacing(8)

        lbl_pub_desc = QLabel("Chave Pública (formato OpenSSH authorized_keys para colar no servidor ou GitHub):")
        v_pub.addWidget(lbl_pub_desc)

        self.text_pub_openssh = QTextEdit()
        self.text_pub_openssh.setReadOnly(True)
        self.text_pub_openssh.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        v_pub.addWidget(self.text_pub_openssh)

        bar_pub = QHBoxLayout()
        btn_copy_pub = QPushButton("Copiar Chave Pública")
        btn_copy_pub.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy_pub.clicked.connect(lambda: self._copy_text(self.text_pub_openssh.toPlainText()))
        bar_pub.addWidget(btn_copy_pub)

        btn_save_pub = QPushButton("Salvar Arquivo (.pub)...")
        btn_save_pub.clicked.connect(self._save_public_key)
        bar_pub.addWidget(btn_save_pub)
        bar_pub.addStretch()
        v_pub.addLayout(bar_pub)
        tabs.addTab(tab_pub, "Chave Pública (.pub)")

        # Tab Chave Privada
        tab_priv = QWidget()
        v_priv = QVBoxLayout(tab_priv)
        v_priv.setSpacing(8)

        lbl_priv_desc = QLabel("Chave Privada (guarde com total sigilo; NUNCA compartilhe publicamente):")
        lbl_priv_desc.setStyleSheet("color: #D83B01; font-weight: bold;")
        v_priv.addWidget(lbl_priv_desc)

        self.text_priv = QTextEdit()
        self.text_priv.setReadOnly(True)
        self.text_priv.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        v_priv.addWidget(self.text_priv)

        bar_priv = QHBoxLayout()
        btn_copy_priv = QPushButton("Copiar Chave Privada")
        btn_copy_priv.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy_priv.clicked.connect(lambda: self._copy_text(self.text_priv.toPlainText()))
        bar_priv.addWidget(btn_copy_priv)

        btn_save_priv = QPushButton("Salvar Chave Privada...")
        btn_save_priv.clicked.connect(self._save_private_key)
        bar_priv.addWidget(btn_save_priv)
        bar_priv.addStretch()
        v_priv.addLayout(bar_priv)
        tabs.addTab(tab_priv, "Chave Privada (Privada)")

        layout.addWidget(tabs, 1)

        # Gerar chave inicial Ed25519
        self._on_generate()

        return container

    def _on_generate(self) -> None:
        algo = self.combo_algo.currentData()
        comment = self.edit_comment.text().strip()
        passphrase = self.edit_pass.text() or None

        try:
            pair = generate_key_pair(
                algorithm=algo,
                passphrase=passphrase,
                comment=comment,
            )
            self._current_key_pair = pair

            self.lbl_fp_sha256.setText(pair.fingerprint_sha256)
            self.lbl_fp_md5.setText(pair.fingerprint_md5)
            self.text_pub_openssh.setPlainText(pair.public_key_openssh)
            self.text_priv.setPlainText(pair.private_key_openssh)

        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao gerar par de chaves: {e}")

    def _copy_text(self, text: str) -> None:
        if text and text != "-":
            cb = QApplication.clipboard()
            if cb:
                cb.setText(text)

    def _save_public_key(self) -> None:
        if not self._current_key_pair:
            return
        algo = self._current_key_pair.algorithm
        default_name = f"id_{algo}.pub"
        path, _ = QFileDialog.getSaveFileName(None, "Salvar Chave Pública", default_name, "Chave Pública (*.pub);;Todos (*.*)")
        if path:
            Path(path).write_text(self._current_key_pair.public_key_openssh, encoding="utf-8")

    def _save_private_key(self) -> None:
        if not self._current_key_pair:
            return
        algo = self._current_key_pair.algorithm
        default_name = f"id_{algo}"
        path, _ = QFileDialog.getSaveFileName(None, "Salvar Chave Privada", default_name, "Chave Privada (*);;Todos (*.*)")
        if path:
            Path(path).write_text(self._current_key_pair.private_key_openssh, encoding="utf-8")
