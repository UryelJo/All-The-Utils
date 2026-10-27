"""
Interface gráfica Fluent da ferramenta Inspetor e Conversor de Certificados Digitais.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from wintoolbox.core.registry import FileTool, TaskContext, register
from wintoolbox.tools.encode.cert_inspector.logic import (
    convert_cert_to_pem,
    parse_certificate_file,
)


@register
class CertInspectorTool(FileTool):
    """Ferramenta em lote para inspeção, validação e conversão de certificados digitais."""
    id = "encode.cert_inspector"
    title = "Inspetor de Certificados"
    category = "Codificação e Hash"
    description = (
        "Inspeciona, decodifica e converte certificados digitais nos formatos PEM, DER, CRT, CER, "
        "PFX e P12, extraindo titular, emissor, SANs, período de validade e impressões digitais."
    )
    icon = "Certificate"
    supported_extensions = [".crt", ".cer", ".pem", ".pfx", ".p12", ".der"]
    output_extension = ".txt"

    def build_options(self, parent: QWidget | None = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Relatório Detalhado de Metadados (.txt)", "report")
        self.combo_mode.addItem("Converter e Exportar como PEM (.pem)", "pem")
        layout.addRow("Modo de Processamento:", self.combo_mode)

        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_password.setPlaceholderText("Obrigatório apenas para arquivos .pfx / .p12 protegidos")
        layout.addRow("Senha do Certificado (PFX/P12):", self.edit_password)

        return widget

    def get_options(self) -> dict:
        mode = "report"
        pwd = ""
        if hasattr(self, "combo_mode"):
            mode = self.combo_mode.currentData() or "report"
        if hasattr(self, "edit_password"):
            pwd = self.edit_password.text().strip()

        return {
            "mode": mode,
            "password": pwd,
        }

    def process(
        self,
        source_path: Path,
        output_path: Path,
        options: dict,
        context: TaskContext,
    ) -> bool:
        mode = options.get("mode", "report")
        password = options.get("password") or None

        context.log("info", f"Inspecionando certificado: {source_path.name}")

        if mode == "pem":
            pem_out = output_path.with_suffix(".pem")
            success = convert_cert_to_pem(source_path, pem_out, password=password)
            if success:
                context.log("info", f"Certificado convertido para PEM: {pem_out.name}")
                return True
            else:
                context.log("error", f"Falha ao converter {source_path.name} para PEM.")
                return False

        # Modo Relatório de Metadados (.txt)
        info = parse_certificate_file(source_path, password=password)
        if not info.is_valid_format:
            context.log("error", f"{source_path.name}: {info.error_message}")
            return False

        status_validade = "EXPIRADO" if info.is_expired else f"VÁLIDO ({info.days_remaining} dias restantes)"
        nb_str = info.not_before.strftime("%d/%m/%Y %H:%M:%S UTC") if info.not_before else "N/A"
        na_str = info.not_after.strftime("%d/%m/%Y %H:%M:%S UTC") if info.not_after else "N/A"
        sans_str = ", ".join(info.subject_alt_names) if info.subject_alt_names else "Nenhum"

        report = (
            "====================================================\n"
            f" RELATÓRIO DO CERTIFICADO DIGITAL: {source_path.name}\n"
            "====================================================\n\n"
            f"Status de Validade: {status_validade}\n"
            f"Válido a partir de: {nb_str}\n"
            f"Válido até:         {na_str}\n\n"
            "--- TITULAR (SUBJECT) ---\n"
            f"Common Name (CN):   {info.subject_cn}\n"
            f"Organização (O):    {info.subject_org}\n\n"
            "--- EMISSOR (ISSUER / CA) ---\n"
            f"Common Name (CN):   {info.issuer_cn}\n"
            f"Organização (O):    {info.issuer_org}\n\n"
            "--- DETALHES TÉCNICOS ---\n"
            f"Número de Série:    {info.serial_number_hex}\n"
            f"Algoritmo:          {info.signature_algorithm}\n"
            f"Tipo da Chave:      {info.public_key_type} ({info.public_key_bits} bits)\n"
            f"Nomes Alternativos: {sans_str}\n\n"
            "--- IMPRESSÕES DIGITAIS (THUMBPRINTS) ---\n"
            f"SHA-256: {info.sha256_thumbprint}\n"
            f"SHA-1:   {info.sha1_thumbprint}\n"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        context.log("info", f"Relatório gravado em {output_path.name}")
        return True
