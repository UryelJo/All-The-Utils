"""
Interface de usuário para a ferramenta Gerador de Certificados SSL/TLS Autoassinados.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.selfsigned_cert.logic import (
    CertificateResult,
    export_pkcs12_pfx,
    generate_self_signed_cert,
)


@register
class SelfSignedCertTool(Tool):
    """Gerador de certificados SSL/TLS autoassinados e CAs locais para testes de desenvolvimento."""

    id = "dev.selfsigned_cert"
    name = "Gerador de Certificados SSL/TLS (Self-Signed)"
    description = "Cria certificados SSL/TLS autoassinados e CAs locais com SANs customizados (localhost, IPs) para testes e desenvolvimento."
    category = "dev"

    def __init__(self):
        super().__init__()
        self.last_result: Optional[CertificateResult] = None

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("Gerador de Certificados SSL/TLS Autoassinados")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Gere pares de certificados X.509 e chaves privadas criptográficas com suporte a múltiplos "
            "Subject Alternative Names (SANs) para ambientes de teste, microsserviços e APIs locais."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Painel de Parâmetros
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(form_frame)
        grid.setSpacing(10)

        # Common Name (CN)
        grid.addWidget(QLabel("Common Name (CN):"), 0, 0)
        self.txt_cn = QLineEdit("localhost")
        self.txt_cn.setPlaceholderText("Ex: localhost ou api.empresa.local")
        grid.addWidget(self.txt_cn, 0, 1)

        # Organização
        grid.addWidget(QLabel("Organização (O):"), 0, 2)
        self.txt_org = QLineEdit("WinToolbox Desenvolvimento")
        grid.addWidget(self.txt_org, 0, 3)

        # Subject Alternative Names (SANs)
        grid.addWidget(QLabel("SANs (Separados por vírgula):"), 1, 0)
        self.txt_sans = QLineEdit("localhost, 127.0.0.1, ::1")
        self.txt_sans.setPlaceholderText("Ex: localhost, 127.0.0.1, 192.168.1.10, *.local")
        grid.addWidget(self.txt_sans, 1, 1, 1, 3)

        # Validade e Algoritmo
        grid.addWidget(QLabel("Validade em Dias:"), 2, 0)
        self.spin_validity = QSpinBox()
        self.spin_validity.setRange(1, 7300)
        self.spin_validity.setValue(365)
        self.spin_validity.setSuffix(" dias")
        grid.addWidget(self.spin_validity, 2, 1)

        grid.addWidget(QLabel("Algoritmo da Chave:"), 2, 2)
        self.combo_algo = QComboBox()
        self.combo_algo.addItem("RSA 2048 bits (Mais Compatível)", "RSA_2048")
        self.combo_algo.addItem("RSA 4096 bits (Alta Segurança)", "RSA_4096")
        self.combo_algo.addItem("ECDSA P-256 (Mais Rápido e Leve)", "ECDSA_P256")
        self.combo_algo.addItem("ECDSA P-384", "ECDSA_P384")
        grid.addWidget(self.combo_algo, 2, 3)

        # Checkbox CA
        self.chk_ca = QCheckBox("Gerar como Autoridade Certificadora Raiz (Root CA)")
        self.chk_ca.setToolTip(
            "Se marcado, adiciona extensões x509 Basic Constraints CA=True e permissão de assinatura de certificados."
        )
        grid.addWidget(self.chk_ca, 3, 0, 1, 4)

        layout.addWidget(form_frame)

        # Botão Gerar
        self.btn_generate = QPushButton("Gerar Certificado e Chave Privada")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_generate.clicked.connect(self._generate_cert)
        layout.addWidget(self.btn_generate)

        # Abas de Visualização dos Resultados
        self.tabs = QTabWidget()

        # Aba Certificado
        self.tab_cert = QWidget()
        v_cert = QVBoxLayout(self.tab_cert)
        self.txt_cert_pem = QTextEdit()
        self.txt_cert_pem.setFont(QFont("Consolas", 10))
        self.txt_cert_pem.setReadOnly(True)
        v_cert.addWidget(self.txt_cert_pem)
        self.tabs.addTab(self.tab_cert, "Certificado (cert.pem)")

        # Aba Chave Privada
        self.tab_key = QWidget()
        v_key = QVBoxLayout(self.tab_key)
        self.txt_key_pem = QTextEdit()
        self.txt_key_pem.setFont(QFont("Consolas", 10))
        self.txt_key_pem.setReadOnly(True)
        v_key.addWidget(self.txt_key_pem)
        self.tabs.addTab(self.tab_key, "Chave Privada (key.pem)")

        # Aba Resumo
        self.tab_summary = QWidget()
        v_sum = QVBoxLayout(self.tab_summary)
        self.txt_summary = QTextEdit()
        self.txt_summary.setFont(QFont("Consolas", 10))
        self.txt_summary.setReadOnly(True)
        v_sum.addWidget(self.txt_summary)
        self.tabs.addTab(self.tab_summary, "Resumo e Metadados")

        layout.addWidget(self.tabs, 1)

        # Barra de Ações Inferior
        actions_layout = QHBoxLayout()
        self.btn_copy_active = QPushButton("Copiar Conteúdo da Aba")
        self.btn_copy_active.setEnabled(False)
        self.btn_copy_active.clicked.connect(self._copy_active_tab)

        self.btn_save_pem = QPushButton("Salvar Arquivos PEM (.crt/.key)...")
        self.btn_save_pem.setEnabled(False)
        self.btn_save_pem.clicked.connect(self._save_pems)

        self.btn_export_pfx = QPushButton("Exportar Pacote PFX / PKCS#12...")
        self.btn_export_pfx.setEnabled(False)
        self.btn_export_pfx.clicked.connect(self._export_pfx)

        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_copy_active)
        actions_layout.addWidget(self.btn_save_pem)
        actions_layout.addWidget(self.btn_export_pfx)
        layout.addLayout(actions_layout)

        return widget

    def _generate_cert(self):
        cn = self.txt_cn.text().strip()
        org = self.txt_org.text().strip()
        sans = [s.strip() for s in self.txt_sans.text().split(",") if s.strip()]
        days = self.spin_validity.value()
        algo = self.combo_algo.currentData()
        is_ca = self.chk_ca.isChecked()

        try:
            res = generate_self_signed_cert(
                common_name=cn,
                organization=org,
                san_list=sans,
                validity_days=days,
                key_type=algo,
                is_ca=is_ca
            )
            self.last_result = res

            self.txt_cert_pem.setText(res.cert_pem)
            self.txt_key_pem.setText(res.key_pem)

            summary_text = (
                f"Subject CN: {res.subject_cn}\n"
                f"Impressão Digital SHA-256 (Fingerprint):\n  {res.fingerprint_sha256}\n\n"
                f"Válido de: {res.valid_from.strftime('%d/%m/%Y %H:%M:%S UTC')}\n"
                f"Válido até: {res.valid_to.strftime('%d/%m/%Y %H:%M:%S UTC')}\n\n"
                f"Nomes Alternativos (SANs):\n  " + ", ".join(res.san_list) + "\n\n"
                f"Tipo de Autoridade: {'Root CA (Autoridade Certificadora)' if is_ca else 'Certificado Final (Servidor/Cliente)'}\n"
                f"Algoritmo: {algo}"
            )
            self.txt_summary.setText(summary_text)

            self.btn_copy_active.setEnabled(True)
            self.btn_save_pem.setEnabled(True)
            self.btn_export_pfx.setEnabled(True)

            QMessageBox.information(
                None, "Certificado Criado", "O certificado SSL e a chave privada foram gerados com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha na geração do certificado: {e}")

    def _copy_active_tab(self):
        idx = self.tabs.currentIndex()
        text = ""
        if idx == 0:
            text = self.txt_cert_pem.toPlainText()
        elif idx == 1:
            text = self.txt_key_pem.toPlainText()
        else:
            text = self.txt_summary.toPlainText()

        if text:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(None, "Copiado", "Conteúdo copiado para a área de transferência!")

    def _save_pems(self):
        if not self.last_result:
            return

        folder = QFileDialog.getExistingDirectory(None, "Selecionar Pasta para Salvar Certificado e Chave")
        if not folder:
            return

        dest_dir = Path(folder)
        cert_path = dest_dir / f"{self.last_result.subject_cn}.crt"
        key_path = dest_dir / f"{self.last_result.subject_cn}.key"

        try:
            cert_path.write_text(self.last_result.cert_pem, encoding="utf-8")
            key_path.write_text(self.last_result.key_pem, encoding="utf-8")
            QMessageBox.information(
                None, "Salvo", f"Arquivos salvos com sucesso em:\n{cert_path.name}\n{key_path.name}"
            )
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao salvar arquivos: {e}")

    def _export_pfx(self):
        if not self.last_result:
            return

        dest, _ = QFileDialog.getSaveFileName(
            None, "Exportar Certificado PKCS#12 (PFX)",
            f"{self.last_result.subject_cn}.pfx",
            "Certificado PKCS#12 (*.pfx *.p12)"
        )
        if not dest:
            return

        pwd, ok = QInputDialog.getText(
            None, "Senha do PFX", "Digite uma senha para proteger o arquivo PFX (opcional):",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        try:
            export_pkcs12_pfx(
                cert_pem=self.last_result.cert_pem,
                key_pem=self.last_result.key_pem,
                output_path=Path(dest),
                password=pwd if pwd else None,
                name=self.last_result.subject_cn
            )
            QMessageBox.information(None, "PFX Exportado", f"Arquivo PFX gerado com sucesso em:\n{dest}")
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha ao exportar PFX: {e}")
