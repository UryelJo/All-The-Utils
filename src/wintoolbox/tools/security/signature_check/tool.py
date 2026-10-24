"""
Interface gráfica do Verificador de Assinatura Digital Authenticode.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.security.signature_check.logic import check_authenticode_signature
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("security.signature_check.ui")


@register
class SignatureCheckTool(Tool):
    id = "security.signature_check"
    name = "Verificador de Assinatura Digital"
    category = "Segurança"
    description = "Validação da assinatura Authenticode de executáveis, DLLs e instaladores (empresa emissora e integridade)"
    keywords = ["assinatura digital", "authenticode", "certificado", "exe", "dll", "msi", "seguranca", "valido", "falsificado"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SignatureCheckView(self, parent)


class SignatureCheckView(QWidget):
    def __init__(self, tool: SignatureCheckTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._last_result: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Seletor de arquivo
        card_sel = QFrame()
        card_sel.setObjectName("Card")
        sel_lay = QVBoxLayout(card_sel)
        sel_lay.setContentsMargins(14, 14, 14, 14)
        sel_lay.setSpacing(10)

        sel_lay.addWidget(QLabel("Selecione o arquivo para auditar a assinatura digital (.exe, .dll, .sys, .msi):"))

        row = QHBoxLayout()
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Caminho do arquivo...")
        self.txt_path.returnPressed.connect(self._verify_async)
        row.addWidget(self.txt_path, stretch=1)

        btn_browse = QPushButton("Procurar Arquivo...")
        btn_browse.clicked.connect(self._browse_file)
        row.addWidget(btn_browse)

        self.btn_check = QPushButton("Verificar Assinatura")
        self.btn_check.setProperty("accent", True)
        self.btn_check.clicked.connect(self._verify_async)
        row.addWidget(self.btn_check)

        sel_lay.addLayout(row)
        layout.addWidget(card_sel)

        # Card de Resultado
        self.card_result = QFrame()
        self.card_result.setObjectName("Card")
        res_lay = QVBoxLayout(self.card_result)
        res_lay.setContentsMargins(16, 16, 16, 16)
        res_lay.setSpacing(12)

        top_res = QHBoxLayout()
        self.lbl_file_title = QLabel("Nenhum arquivo analisado")
        self.lbl_file_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        top_res.addWidget(self.lbl_file_title)

        top_res.addStretch()
        self.lbl_badge = QLabel("Aguardando")
        top_res.addWidget(self.lbl_badge)
        res_lay.addLayout(top_res)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Assinante / Empresa:"), 0, 0)
        self.lbl_signer = QLabel("-")
        self.lbl_signer.setWordWrap(True)
        grid.addWidget(self.lbl_signer, 0, 1)

        grid.addWidget(QLabel("Autoridade Certificadora (Emissor):"), 1, 0)
        self.lbl_issuer = QLabel("-")
        self.lbl_issuer.setWordWrap(True)
        grid.addWidget(self.lbl_issuer, 1, 1)

        grid.addWidget(QLabel("Impressão Digital (Thumbprint):"), 2, 0)
        self.lbl_thumbprint = QLabel("-")
        self.lbl_thumbprint.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace;")
        grid.addWidget(self.lbl_thumbprint, 2, 1)

        grid.addWidget(QLabel("Validade do Certificado:"), 3, 0)
        self.lbl_validity = QLabel("-")
        grid.addWidget(self.lbl_validity, 3, 1)

        res_lay.addLayout(grid)

        # Botão de cópia
        self.btn_copy = QPushButton("Copiar Informações da Assinatura")
        self.btn_copy.setFixedWidth(240)
        self.btn_copy.clicked.connect(self._copy_info)
        res_lay.addWidget(self.btn_copy)

        layout.addWidget(self.card_result)
        layout.addStretch()

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Executável para Verificar Assinatura",
            "",
            "Binários do Windows (*.exe *.dll *.sys *.msi);;Todos os Arquivos (*.*)"
        )
        if p:
            self.txt_path.setText(p)
            self._verify_async()

    def _verify_async(self) -> None:
        p_str = self.txt_path.text().strip()
        if not p_str or not Path(p_str).is_file():
            show_toast(self, "Selecione um arquivo existente.", is_error=True)
            return

        self.btn_check.setEnabled(False)
        self.lbl_file_title.setText(f"Analisando {Path(p_str).name}...")

        def _worker():
            return check_authenticode_signature(Path(p_str))

        def _on_done(res: Dict[str, Any]):
            self.btn_check.setEnabled(True)
            self._last_result = res

            self.lbl_file_title.setText(f"Arquivo: {res['file_name']}")

            if res["is_valid"]:
                self.lbl_badge.setText("Assinatura Válida")
                self.lbl_badge.setStyleSheet("background-color: #107c41; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
            elif res["raw_status"] == "NotSigned":
                self.lbl_badge.setText("Não Assinado")
                self.lbl_badge.setStyleSheet("background-color: #797979; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
            else:
                self.lbl_badge.setText(res["status_label"])
                self.lbl_badge.setStyleSheet("background-color: #d83b01; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;")

            self.lbl_signer.setText(res["signer"])
            self.lbl_issuer.setText(res["issuer"])
            self.lbl_thumbprint.setText(res["thumbprint"])
            self.lbl_validity.setText(res["valid_until"])

            show_toast(self, f"Status: {res['status_label']}")

        def _on_error(err):
            self.btn_check.setEnabled(True)
            show_toast(self, f"Erro: {err}", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _copy_info(self) -> None:
        if not self._last_result:
            show_toast(self, "Nenhuma informação para copiar.", is_error=True)
            return

        r = self._last_result
        text = (
            f"Arquivo: {r['file_name']}\n"
            f"Status: {r['status_label']}\n"
            f"Assinante: {r['signer']}\n"
            f"Emissor: {r['issuer']}\n"
            f"Thumbprint: {r['thumbprint']}\n"
            f"Validade: {r['valid_until']}"
        )
        QApplication.clipboard().setText(text)
        show_toast(self, "Dados da assinatura copiados!")
